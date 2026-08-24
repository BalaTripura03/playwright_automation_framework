"""Unit/API tests for the n8n Flask webhook (integrations/n8n_webhook.py).

Runs entirely against Flask's test client with `subprocess.run` mocked out, so no real pytest
subprocess, Ollama call, or browser is ever launched. Uses tmp_path-based BUGS_DIR/LAST_RUN_FILE/
LAST_RERUN_FILE per test (via monkeypatch) so nothing here touches real reports/ data.
"""
import importlib
import json
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.integration

SECRET = "test-secret-123"


@pytest.fixture
def webhook_module(monkeypatch, tmp_path):
    """Imports (or reloads) the webhook module with an isolated secret and isolated report paths."""
    monkeypatch.setenv("N8N_WEBHOOK_SECRET", SECRET)
    from integrations import n8n_webhook as module
    from ai import bug_reporter

    importlib.reload(module)
    bugs_dir = tmp_path / "bugs"
    bugs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(module, "BUGS_DIR", bugs_dir)
    monkeypatch.setattr(module, "LAST_RUN_FILE", tmp_path / "last_run.json")
    monkeypatch.setattr(module, "LAST_RERUN_FILE", tmp_path / "last_rerun.json")
    # find_bugs_for_test/update_bug_status live in ai.bug_reporter with their own BUGS_DIR constant.
    monkeypatch.setattr(bug_reporter, "BUGS_DIR", bugs_dir)
    return module


@pytest.fixture
def client(webhook_module):
    webhook_module.app.testing = True
    return webhook_module.app.test_client()


@pytest.fixture
def auth_headers():
    return {"X-Webhook-Secret": SECRET}


def _fake_pytest_result(stdout: str, returncode: int):
    return SimpleNamespace(stdout=stdout, returncode=returncode)


# ---------------------------------------------------------------------------
# Auth / health
# ---------------------------------------------------------------------------

def test_health_does_not_require_secret(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


@pytest.mark.parametrize("path", [
    "/webhook/run-tests",
    "/webhook/analyze-last-run",
    "/webhook/show-bugs",
    "/webhook/get-bug",
    "/webhook/rerun-failed",
    "/webhook/generate-report",
])
def test_routes_reject_missing_secret(client, path):
    resp = client.get(path)
    assert resp.status_code == 401


def test_routes_reject_wrong_secret(client):
    resp = client.get("/webhook/show-bugs", headers={"X-Webhook-Secret": "wrong"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def test_validate_path_accepts_subdirectory(webhook_module):
    result = webhook_module._validate_path("tests/ui")
    assert result.name == "ui"


def test_validate_path_rejects_traversal(webhook_module):
    with pytest.raises(ValueError):
        webhook_module._validate_path("../../etc")


def test_validate_markers_rejects_unsafe_characters(webhook_module):
    with pytest.raises(ValueError):
        webhook_module._validate_markers("ui; rm -rf /")


def test_validate_markers_allows_boolean_expression(webhook_module):
    assert webhook_module._validate_markers("ui and smoke") == "ui and smoke"


def test_extract_failed_tests_parses_short_summary(webhook_module):
    stdout = (
        "===== short test summary info =====\n"
        "FAILED tests/db/test_x.py::test_one - AssertionError: boom\n"
        "FAILED tests/api/test_y.py::test_two\n"
    )
    assert webhook_module._extract_failed_tests(stdout) == [
        "tests/db/test_x.py::test_one",
        "tests/api/test_y.py::test_two",
    ]


@pytest.mark.parametrize("confidence,expected", [(0.9, "high"), (0.8, "high"), (0.6, "medium"), (0.5, "medium"), (0.1, "low")])
def test_severity_from_confidence(webhook_module, confidence, expected):
    assert webhook_module._severity_from_confidence(confidence) == expected


# ---------------------------------------------------------------------------
# /webhook/run-tests
# ---------------------------------------------------------------------------

def test_run_tests_rejects_bad_path(client, auth_headers):
    resp = client.post("/webhook/run-tests", json={"path": "../outside"}, headers=auth_headers)
    assert resp.status_code == 400


def test_run_tests_passing_run(client, auth_headers, webhook_module, monkeypatch):
    monkeypatch.setattr(
        webhook_module.subprocess, "run",
        lambda *a, **k: _fake_pytest_result("2 passed in 1.23s\n", 0),
    )
    resp = client.post(
        "/webhook/run-tests",
        json={"message": "Run the framework tests", "path": "tests/framework"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["request"] == "Run the framework tests"
    assert body["execution"]["passed"] is True
    assert body["execution"]["passed_count"] == 2
    assert body["execution"]["failed_count"] == 0
    assert body["failed_tests"] == []
    assert webhook_module.LAST_RUN_FILE.exists()


def test_run_tests_failing_run_persists_failed_tests(client, auth_headers, webhook_module, monkeypatch):
    stdout = (
        "===== short test summary info =====\n"
        "FAILED tests/db/test_x.py::test_one - AssertionError\n"
        "1 failed in 1.00s\n"
    )
    monkeypatch.setattr(webhook_module.subprocess, "run", lambda *a, **k: _fake_pytest_result(stdout, 1))
    resp = client.post("/webhook/run-tests", json={"path": "tests/db"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["execution"]["passed"] is False
    assert body["failed_tests"] == ["tests/db/test_x.py::test_one"]
    saved = json.loads(webhook_module.LAST_RUN_FILE.read_text())
    assert saved["failed_tests"] == ["tests/db/test_x.py::test_one"]


# ---------------------------------------------------------------------------
# /webhook/analyze-last-run
# ---------------------------------------------------------------------------

def test_analyze_last_run_with_no_history(client, auth_headers):
    resp = client.get("/webhook/analyze-last-run", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["analyzed"] is False


def test_analyze_last_run_after_a_run(client, auth_headers, webhook_module, monkeypatch):
    monkeypatch.setattr(webhook_module.subprocess, "run", lambda *a, **k: _fake_pytest_result("1 passed\n", 0))
    client.post("/webhook/run-tests", json={"path": "tests/framework"}, headers=auth_headers)

    resp = client.get("/webhook/analyze-last-run", headers=auth_headers)
    body = resp.get_json()
    assert body["analyzed"] is True
    assert "passed" in body["summary"]


# ---------------------------------------------------------------------------
# Bug management: show-bugs / get-bug
# ---------------------------------------------------------------------------

def _write_bug(webhook_module, bug_id, **overrides):
    bug = {
        "id": bug_id,
        "test_name": "tests/db/test_x.py::test_one",
        "created_at": "2026-01-01T00:00:00",
        "category": "app_bug",
        "confidence": 0.9,
        "explanation": "Example failure",
        "evidence": {},
        "status": "open",
    }
    bug.update(overrides)
    (webhook_module.BUGS_DIR / f"{bug_id}.json").write_text(json.dumps(bug), encoding="utf-8")
    return bug


def test_show_bugs_empty(client, auth_headers):
    resp = client.get("/webhook/show-bugs", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.get_json()["count"] == 0


def test_show_bugs_filters_by_severity(client, auth_headers, webhook_module):
    _write_bug(webhook_module, "BUG-aaaaaaaaaaaa", confidence=0.9)  # high
    _write_bug(webhook_module, "BUG-bbbbbbbbbbbb", confidence=0.3)  # low

    resp = client.get("/webhook/show-bugs?severity=high", headers=auth_headers)
    body = resp.get_json()
    assert body["count"] == 1
    assert body["bugs"][0]["id"] == "BUG-aaaaaaaaaaaa"


def test_show_bugs_rejects_invalid_severity(client, auth_headers):
    resp = client.get("/webhook/show-bugs?severity=critical", headers=auth_headers)
    assert resp.status_code == 400


def test_get_bug_found(client, auth_headers, webhook_module):
    _write_bug(webhook_module, "BUG-cccccccccccc")
    resp = client.get("/webhook/get-bug?bug_id=BUG-cccccccccccc", headers=auth_headers)
    body = resp.get_json()
    assert body["found"] is True
    assert body["bug"]["id"] == "BUG-cccccccccccc"


def test_get_bug_not_found(client, auth_headers):
    resp = client.get("/webhook/get-bug?bug_id=BUG-000000000000", headers=auth_headers)
    body = resp.get_json()
    assert body["found"] is False


def test_get_bug_rejects_malformed_id(client, auth_headers):
    resp = client.get("/webhook/get-bug?bug_id=not-a-bug-id", headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /webhook/rerun-failed - lifecycle status transitions
# ---------------------------------------------------------------------------

def test_rerun_failed_with_no_last_run(client, auth_headers):
    resp = client.get("/webhook/rerun-failed", headers=auth_headers)
    body = resp.get_json()
    assert body["rerun"] is False


def test_rerun_failed_marks_bug_resolved(client, auth_headers, webhook_module, monkeypatch):
    _write_bug(webhook_module, "BUG-dddddddddddd", status="open")
    webhook_module._save_last_run({
        "request": "Run the DB tests",
        "route": {"suite": "db", "path": "tests/db", "markers": ""},
        "execution": {"passed": False, "exit_code": 1, "passed_count": 0, "failed_count": 1, "duration": 1.0},
        "analysis": {"performed": True, "bugs_filed": 1},
        "bugs": [{"id": "BUG-dddddddddddd", "severity": "high", "confidence": 0.9, "category": "app_bug", "explanation": "x", "status": "open"}],
        "failed_tests": ["tests/db/test_x.py::test_one"],
        "stdout_tail": "",
    })
    monkeypatch.setattr(webhook_module.subprocess, "run", lambda *a, **k: _fake_pytest_result("1 passed\n", 0))

    resp = client.get("/webhook/rerun-failed", headers=auth_headers)
    body = resp.get_json()
    assert body["resolved"] == ["tests/db/test_x.py::test_one"]

    updated_bug = json.loads((webhook_module.BUGS_DIR / "BUG-dddddddddddd.json").read_text())
    assert updated_bug["status"] == "resolved"


def test_rerun_failed_marks_bug_still_failing(client, auth_headers, webhook_module, monkeypatch):
    _write_bug(webhook_module, "BUG-eeeeeeeeeeee", status="open")
    webhook_module._save_last_run({
        "request": "Run the DB tests",
        "route": {"suite": "db", "path": "tests/db", "markers": ""},
        "execution": {"passed": False, "exit_code": 1, "passed_count": 0, "failed_count": 1, "duration": 1.0},
        "analysis": {"performed": True, "bugs_filed": 1},
        "bugs": [{"id": "BUG-eeeeeeeeeeee", "severity": "high", "confidence": 0.9, "category": "app_bug", "explanation": "x", "status": "open"}],
        "failed_tests": ["tests/db/test_x.py::test_one"],
        "stdout_tail": "",
    })
    stdout = "FAILED tests/db/test_x.py::test_one - AssertionError\n1 failed\n"
    monkeypatch.setattr(webhook_module.subprocess, "run", lambda *a, **k: _fake_pytest_result(stdout, 1))

    resp = client.get("/webhook/rerun-failed", headers=auth_headers)
    body = resp.get_json()
    assert body["still_failing"] == ["tests/db/test_x.py::test_one"]

    updated_bug = json.loads((webhook_module.BUGS_DIR / "BUG-eeeeeeeeeeee.json").read_text())
    assert updated_bug["status"] == "still_failing"


def test_rerun_failed_rejects_malformed_test_id(client, auth_headers, webhook_module):
    webhook_module._save_last_run({
        "request": "x", "route": {"suite": "db"}, "execution": {}, "analysis": {}, "bugs": [],
        "failed_tests": ["not-a-valid-test-id"], "stdout_tail": "",
    })
    resp = client.get("/webhook/rerun-failed", headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /webhook/generate-report
# ---------------------------------------------------------------------------

def test_generate_report_with_no_history(client, auth_headers):
    resp = client.get("/webhook/generate-report", headers=auth_headers)
    body = resp.get_json()
    assert body["generated"] is False


def test_generate_report_reflects_persisted_bug_status(client, auth_headers, webhook_module):
    _write_bug(webhook_module, "BUG-ffffffffffff", status="resolved")
    webhook_module._save_last_run({
        "request": "Run the DB tests",
        "route": {"suite": "db", "path": "tests/db", "markers": ""},
        "execution": {"passed": False, "exit_code": 1, "passed_count": 0, "failed_count": 1, "duration": 5.0},
        "analysis": {"performed": True, "bugs_filed": 1},
        "bugs": [{"id": "BUG-ffffffffffff", "severity": "high", "confidence": 0.9, "category": "app_bug", "explanation": "x", "status": "open"}],
        "failed_tests": ["tests/db/test_x.py::test_one"],
        "stdout_tail": "",
    })

    resp = client.get("/webhook/generate-report", headers=auth_headers)
    body = resp.get_json()
    assert body["generated"] is True
    assert body["bugs"][0]["status"] == "resolved"
    assert "Test Execution Report" in body["report_text"]
