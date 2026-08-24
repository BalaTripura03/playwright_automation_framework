"""Flask webhook server letting n8n (or any external orchestrator) trigger pytest runs over HTTP.

Security:
- Every request (except /health) must include a matching `X-Webhook-Secret` header, whose
  expected value comes from the N8N_WEBHOOK_SECRET environment variable. The server refuses to
  start at all if that variable isn't set (fail-closed).
- `path` is validated to resolve inside the tests/ directory (no path traversal).
- `markers` is restricted to a safe character set before being passed to pytest.
- pytest is invoked via subprocess with a list of args (never shell=True), so no shell injection
  is possible through user-supplied values.
- Binds to 127.0.0.1 by default; only widen WEBHOOK_HOST if you understand the exposure.

Run with: python -m integrations.n8n_webhook
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests
from flask import Flask, jsonify, request

from ai.bug_reporter import find_bugs_for_test, update_bug_status
from utils.logger import get_logger

logger = get_logger(__name__)

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
TESTS_ROOT = PROJECT_ROOT / "tests"
BUGS_DIR = PROJECT_ROOT / "reports" / "bugs"
LAST_RUN_FILE = PROJECT_ROOT / "reports" / "last_run.json"
LAST_RERUN_FILE = PROJECT_ROOT / "reports" / "last_rerun.json"

WEBHOOK_SECRET = os.getenv("N8N_WEBHOOK_SECRET")

_SAFE_MARKER_RE = re.compile(r"^[A-Za-z0-9_ ()]*$")
_SUMMARY_RE = re.compile(r"(\d+) (passed|failed|error|skipped|xfailed|xpassed)")
_FAILED_LINE_RE = re.compile(r"^(?:FAILED|ERROR) (\S+)", re.MULTILINE)
_TEST_ID_RE = re.compile(r"^tests/[A-Za-z0-9_./-]+::[A-Za-z0-9_\[\]./-]+$")
_BUG_ID_RE = re.compile(r"^BUG-[0-9a-fA-F]{12}$")
_VALID_SEVERITIES = {"high", "medium", "low"}


def _validate_path(path_str: str) -> Path:
    candidate = (PROJECT_ROOT / (path_str or "tests")).resolve()
    if candidate != TESTS_ROOT and TESTS_ROOT not in candidate.parents:
        raise ValueError("'path' must resolve inside the tests/ directory")
    return candidate


def _validate_markers(markers: str) -> str:
    markers = markers or ""
    if not _SAFE_MARKER_RE.match(markers):
        raise ValueError("'markers' contains disallowed characters")
    return markers


def _parse_summary(output: str) -> dict:
    return {status: int(count) for count, status in _SUMMARY_RE.findall(output)}


def _suite_name(path: Path) -> str:
    """Derives a short suite label from the resolved path, e.g. tests/api -> 'api', tests -> 'all'."""
    relative = path.relative_to(PROJECT_ROOT).as_posix()
    return relative.split("/")[-1] if relative != "tests" else "all"


def _severity_from_confidence(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def _extract_failed_tests(stdout: str) -> list[str]:
    """Pulls test node IDs out of pytest's 'FAILED tests/x.py::test_y - ...' short summary lines."""
    seen = []
    for match in _FAILED_LINE_RE.finditer(stdout):
        node_id = match.group(1)
        if node_id not in seen:
            seen.append(node_id)
    return seen


def _summarize_bugs(bug_dicts: list[dict]) -> list[dict]:
    return [
        {
            "id": bug["id"],
            "severity": _severity_from_confidence(bug.get("confidence", 0)),
            "confidence": bug.get("confidence"),
            "category": bug.get("category"),
            "explanation": bug.get("explanation"),
            "status": bug.get("status", "open"),
        }
        for bug in bug_dicts
    ]


def _execute_pytest(command: list[str]) -> dict:
    """Runs a pytest command via subprocess (list args, no shell) and reports what happened."""
    logger.info(f"n8n webhook triggering: {' '.join(command)}")

    # Force AI RCA/bug-filing on for n8n-triggered runs, regardless of the server's own env.
    env = {**os.environ, "AI_ENABLED": "true"}
    BUGS_DIR.mkdir(parents=True, exist_ok=True)
    bugs_before = set(BUGS_DIR.glob("*.json"))

    start = time.time()
    result = subprocess.run(
        command, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=1800, env=env
    )
    duration = round(time.time() - start, 2)

    bugs_after = set(BUGS_DIR.glob("*.json"))
    new_bugs = []
    for bug_file in bugs_after - bugs_before:
        try:
            new_bugs.append(json.loads(bug_file.read_text(encoding="utf-8")))
        except Exception as e:
            logger.error(f"Failed to read bug report {bug_file}: {e}")

    summary = _parse_summary(result.stdout)
    passed_count = summary.get("passed", 0)
    failed_count = summary.get("failed", 0) + summary.get("error", 0)

    return {
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "failed_tests": _extract_failed_tests(result.stdout),
        "duration": duration,
        "new_bugs": new_bugs,
        "stdout": result.stdout,
    }


def _run_pytest(path: Path, markers: str) -> dict:
    command = [sys.executable, "-m", "pytest", str(path)]
    if markers:
        command += ["-m", markers]
    outcome = _execute_pytest(command)

    return {
        "route": {"suite": _suite_name(path), "path": path.relative_to(PROJECT_ROOT).as_posix(), "markers": markers},
        "execution": {
            "passed": outcome["passed"],
            "exit_code": outcome["exit_code"],
            "passed_count": outcome["passed_count"],
            "failed_count": outcome["failed_count"],
            "duration": outcome["duration"],
        },
        "analysis": {"performed": outcome["failed_count"] > 0, "bugs_filed": len(outcome["new_bugs"])},
        "bugs": _summarize_bugs(outcome["new_bugs"]),
        "failed_tests": outcome["failed_tests"],
        "stdout_tail": outcome["stdout"][-2000:],
    }


def _rerun_failed_tests(test_ids: list[str]) -> dict:
    """Reruns exactly the given failed test node IDs (not the whole suite), updates the persisted
    status of any bug filed against them, and reports what changed."""
    command = [sys.executable, "-m", "pytest", *test_ids]
    outcome = _execute_pytest(command)

    resolved = [t for t in test_ids if t not in outcome["failed_tests"]]
    still_failing = [t for t in test_ids if t in outcome["failed_tests"]]

    for test_id in resolved:
        for bug_id in find_bugs_for_test(test_id):
            update_bug_status(bug_id, "resolved")
    for test_id in still_failing:
        for bug_id in find_bugs_for_test(test_id):
            update_bug_status(bug_id, "still_failing")

    if still_failing:
        summary = (
            f"Reran {len(test_ids)} previously failing test(s): {len(resolved)} now pass, "
            f"{len(still_failing)} still failing."
        )
    else:
        summary = f"Reran {len(test_ids)} previously failing test(s): all {len(resolved)} now pass."

    return {
        "rerun": True,
        "attempted": test_ids,
        "resolved": resolved,
        "still_failing": still_failing,
        "execution": {
            "passed": outcome["passed"],
            "exit_code": outcome["exit_code"],
            "passed_count": outcome["passed_count"],
            "failed_count": outcome["failed_count"],
            "duration": outcome["duration"],
        },
        "bugs": _summarize_bugs(outcome["new_bugs"]),
        "summary": summary,
    }


def _post_callback(callback_url: str, payload: dict):
    try:
        requests.post(callback_url, json=payload, timeout=30)
        logger.info(f"Posted results to callback_url: {callback_url}")
    except Exception as e:
        logger.error(f"Failed to post results to callback_url {callback_url}: {e}")


def _save_last_run(data: dict) -> None:
    LAST_RUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_last_run() -> dict | None:
    if not LAST_RUN_FILE.exists():
        return None
    try:
        return json.loads(LAST_RUN_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read {LAST_RUN_FILE}: {e}")
        return None


def _save_last_rerun(data: dict) -> None:
    LAST_RERUN_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_RERUN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_last_rerun() -> dict | None:
    if not LAST_RERUN_FILE.exists():
        return None
    try:
        return json.loads(LAST_RERUN_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read {LAST_RERUN_FILE}: {e}")
        return None


def _load_bug_file(bug_path: Path) -> dict | None:
    try:
        bug = json.loads(bug_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read bug report {bug_path}: {e}")
        return None
    bug["severity"] = _severity_from_confidence(bug.get("confidence", 0))
    bug.setdefault("status", "open")  # bugs filed before status tracking was added
    return bug


def _list_bugs(severity: str | None = None) -> list[dict]:
    bugs = [b for f in BUGS_DIR.glob("BUG-*.json") if (b := _load_bug_file(f)) is not None]
    bugs.sort(key=lambda b: b.get("created_at", ""), reverse=True)
    if severity:
        bugs = [b for b in bugs if b.get("severity") == severity]
    return bugs


def _summarize_last_run(data: dict) -> dict:
    """Builds a natural-language-friendly summary of the last recorded run, for 'why did it fail' style queries."""
    execution = data.get("execution", {})
    route = data.get("route", {})
    bugs = data.get("bugs", [])
    suite = route.get("suite", "unknown")

    if execution.get("passed"):
        summary = f"The last run ({suite} suite) passed - {execution.get('passed_count', 0)} test(s) passed, nothing to analyze."
    else:
        parts = [f"{execution.get('failed_count', 0)} test(s) failed in the last run ({suite} suite)."]
        for bug in bugs:
            parts.append(f"[{bug.get('severity', 'unknown').upper()}] {bug.get('id')}: {bug.get('explanation')}")
        summary = " ".join(parts)

    return {
        "analyzed": True,
        "request": data.get("request"),
        "route": route,
        "execution": execution,
        "summary": summary,
        "bugs": bugs,
    }


@app.before_request
def _check_secret():
    if request.path == "/health":
        return None
    if not WEBHOOK_SECRET or request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/webhook/run-tests", methods=["POST"])
def run_tests():
    """Body: {"message": "...", "path": "tests/ui", "markers": "ui and smoke",
    "callback_url": "...", "async": false}. `message` is optional and echoed back as-is,
    letting callers correlate the response with the original natural-language request."""
    body = request.get_json(silent=True) or {}
    callback_url = body.get("callback_url")
    is_async = bool(body.get("async", False))
    original_request = body.get("message", "")

    try:
        validated_path = _validate_path(body.get("path", "tests"))
        validated_markers = _validate_markers(body.get("markers", ""))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if is_async:
        if not callback_url:
            return jsonify({"error": "callback_url is required when async=true"}), 400

        def _worker():
            result = {"request": original_request, **_run_pytest(validated_path, validated_markers)}
            _save_last_run(result)
            _post_callback(callback_url, result)

        threading.Thread(target=_worker, daemon=True).start()
        return jsonify({"status": "started"}), 202

    result = {"request": original_request, **_run_pytest(validated_path, validated_markers)}
    _save_last_run(result)
    if callback_url:
        _post_callback(callback_url, result)
    return jsonify(result), 200


@app.route("/webhook/analyze-last-run", methods=["GET", "POST"])
def analyze_last_run():
    """Answers 'why did the last test fail?' style queries without re-running anything."""
    data = _load_last_run()
    if data is None:
        return jsonify({
            "analyzed": False,
            "summary": "No test run has been recorded yet. Run a test suite first.",
            "bugs": [],
        }), 200
    return jsonify(_summarize_last_run(data)), 200


@app.route("/webhook/show-bugs", methods=["GET", "POST"])
def show_bugs():
    """Answers 'show me the bugs' / 'show high severity bugs' style queries.
    severity comes from the query string (GET) or JSON body (POST); one of high/medium/low, or
    omitted/empty to return all bugs."""
    severity = (request.values.get("severity") or (request.get_json(silent=True) or {}).get("severity") or "").strip().lower()
    if severity and severity not in _VALID_SEVERITIES:
        return jsonify({"error": f"'severity' must be one of {sorted(_VALID_SEVERITIES)} or empty"}), 400

    bugs = _list_bugs(severity or None)
    label = f"{severity} severity" if severity else "all severities"
    summary = f"Found {len(bugs)} bug(s) ({label})." if bugs else f"No bugs found ({label})."
    return jsonify({"count": len(bugs), "severity_filter": severity or "all", "summary": summary, "bugs": bugs}), 200


@app.route("/webhook/get-bug", methods=["GET", "POST"])
def get_bug():
    """Answers 'give me the details of BUG-xxxx' style queries."""
    bug_id = (request.values.get("bug_id") or (request.get_json(silent=True) or {}).get("bug_id") or "").strip()
    if not _BUG_ID_RE.match(bug_id):
        return jsonify({"error": "'bug_id' must look like BUG-xxxxxxxxxxxx"}), 400

    bug = _load_bug_file(BUGS_DIR / f"{bug_id}.json")
    if bug is None:
        return jsonify({"found": False, "summary": f"No bug found with id {bug_id}."}), 200
    return jsonify({"found": True, "summary": f"{bug_id} ({bug['severity']}): {bug.get('explanation')}", "bug": bug}), 200


@app.route("/webhook/rerun-failed", methods=["GET", "POST"])
def rerun_failed():
    """Answers 'rerun the failed tests' / 'rerun BUG-xxxx' style queries.
    With no bug_id: reruns every test that failed in the last recorded run (from last_run.json).
    With bug_id: reruns only that bug's associated test. Never reruns a whole suite."""
    bug_id = (request.values.get("bug_id") or (request.get_json(silent=True) or {}).get("bug_id") or "").strip()

    if bug_id:
        if not _BUG_ID_RE.match(bug_id):
            return jsonify({"error": "'bug_id' must look like BUG-xxxxxxxxxxxx"}), 400
        bug = _load_bug_file(BUGS_DIR / f"{bug_id}.json")
        if bug is None:
            return jsonify({"rerun": False, "summary": f"No bug found with id {bug_id}."}), 200
        test_ids = [bug["test_name"]]
    else:
        data = _load_last_run()
        if data is None:
            return jsonify({"rerun": False, "summary": "No test run has been recorded yet. Run a test suite first."}), 200
        test_ids = data.get("failed_tests") or []
        if not test_ids:
            suite = data.get("route", {}).get("suite", "unknown")
            return jsonify({"rerun": False, "summary": f"The last run ({suite} suite) had no failing tests to rerun."}), 200

    invalid = [t for t in test_ids if not _TEST_ID_RE.match(t)]
    if invalid:
        return jsonify({"error": f"Refusing to rerun malformed test id(s): {invalid}"}), 400

    result = _rerun_failed_tests(test_ids)
    _save_last_rerun(result)
    return jsonify(result), 200


def _format_report_text(data: dict, rerun: dict | None, bugs: list[dict]) -> str:
    execution = data.get("execution", {})
    route = data.get("route", {})
    analysis = data.get("analysis", {})

    lines = [
        "Test Execution Report",
        "----------------------",
        f"Request: {data.get('request') or 'n/a'}",
        f"Suite: {route.get('suite', 'unknown')}",
        f"Duration: {execution.get('duration', 0)}s",
        "",
        "Results",
        "-------",
        f"Passed: {execution.get('passed_count', 0)}",
        f"Failed: {execution.get('failed_count', 0)}",
        "",
        "Analysis",
        "--------",
        f"RCA performed: {'Yes' if analysis.get('performed') else 'No'}",
        f"Bugs created: {analysis.get('bugs_filed', 0)}",
    ]

    if bugs:
        lines += ["", "Bug Summary", "-----------"]
        for bug in bugs:
            lines.append(f"{bug.get('id')}")
            lines.append(f"  Severity: {bug.get('severity', 'unknown').title()}")
            lines.append(f"  Status: {bug.get('status', 'open').replace('_', ' ').title()}")

    if rerun is not None:
        status = "Still failing" if rerun.get("still_failing") else "Resolved"
        lines += ["", "Rerun", "-----", f"Status: {status}"]

    return "\n".join(lines)


def _generate_report(scope: str) -> dict:
    """Combines the last run's execution, analysis, and bugs (plus a rerun if one happened) into a report."""
    data = _load_last_run()
    if data is None:
        return {
            "generated": False,
            "summary": "No test run has been recorded yet. Run a test suite first.",
        }

    rerun = _load_last_rerun()
    # Only attach the rerun if it targeted the same tests that failed in this run - otherwise it's stale.
    if rerun is not None and set(rerun.get("attempted", [])) != set(data.get("failed_tests", [])):
        rerun = None

    # Reload each bug's current status from disk rather than trusting the snapshot taken at run time,
    # so a rerun's effect on bug status (see _rerun_failed_tests) is reflected accurately.
    bugs = []
    for bug in data.get("bugs", []):
        current = _load_bug_file(BUGS_DIR / f"{bug['id']}.json")
        bugs.append(current if current is not None else bug)

    report_text = _format_report_text(data, rerun, bugs)
    execution = data.get("execution", {})
    summary = (
        f"{data.get('route', {}).get('suite', 'unknown')} suite: "
        f"{execution.get('passed_count', 0)} passed, {execution.get('failed_count', 0)} failed, "
        f"{len(bugs)} bug(s) filed."
    )

    return {
        "generated": True,
        "scope": scope,
        "request": data.get("request"),
        "route": data.get("route"),
        "execution": execution,
        "analysis": data.get("analysis"),
        "bugs": bugs,
        "rerun": rerun,
        "summary": summary,
        "report_text": report_text,
    }


@app.route("/webhook/generate-report", methods=["GET", "POST"])
def generate_report():
    """Answers 'give me a summary of the last run' / 'generate a test report' style queries."""
    scope = (request.values.get("scope") or (request.get_json(silent=True) or {}).get("scope") or "last_run").strip()
    return jsonify(_generate_report(scope)), 200


def main():
    if not WEBHOOK_SECRET:
        logger.error("N8N_WEBHOOK_SECRET is not set - refusing to start the webhook server.")
        raise SystemExit(1)
    host = os.getenv("WEBHOOK_HOST", "127.0.0.1")
    port = int(os.getenv("WEBHOOK_PORT", "5005"))
    logger.info(f"Starting n8n webhook server on {host}:{port}")
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
