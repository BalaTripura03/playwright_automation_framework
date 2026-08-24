"""Auto-creates a local bug report file when root-cause analysis flags a failure as a likely app bug.

Swap `file_bug`'s file-write for a real Jira/Azure DevOps REST API call once tracker credentials
are available - the dedup-by-signature logic and evidence payload stay the same.
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from config.config_reader import ConfigReader
from utils.logger import get_logger

logger = get_logger(__name__)

BUGS_DIR = Path(__file__).parent.parent / "reports" / "bugs"
BUGS_DIR.mkdir(parents=True, exist_ok=True)

VALID_STATUSES = {"open", "resolved", "still_failing"}


def _signature(test_name: str, explanation: str) -> str:
    return hashlib.sha256(f"{test_name}:{explanation}".encode()).hexdigest()[:12]


def file_bug(test_name: str, analysis: dict, evidence: dict) -> str | None:
    """Writes a bug report JSON if the analysis is a confident app_bug classification. Returns the path, or None."""
    threshold = ConfigReader.get("bug_confidence_threshold", 0.6)
    if analysis.get("category") != "app_bug" or analysis.get("confidence", 0) < threshold:
        logger.info(f"Skipping bug creation for {test_name}: category={analysis.get('category')}")
        return None

    sig = _signature(test_name, analysis.get("explanation", ""))
    bug_path = BUGS_DIR / f"BUG-{sig}.json"
    if bug_path.exists():
        logger.info(f"Bug already filed for this failure signature: {bug_path}")
        return str(bug_path)

    bug = {
        "id": f"BUG-{sig}",
        "test_name": test_name,
        "created_at": datetime.now().isoformat(),
        "category": analysis.get("category"),
        "confidence": analysis.get("confidence"),
        "explanation": analysis.get("explanation"),
        "evidence": evidence,
        "status": "open",
    }
    with open(bug_path, "w", encoding="utf-8") as f:
        json.dump(bug, f, indent=2)
    logger.warning(f"Auto-filed bug report: {bug_path}")
    return str(bug_path)


def update_bug_status(bug_id: str, status: str) -> bool:
    """Persists a bug's lifecycle status (open/resolved/still_failing) back to its JSON file. Returns
    True if the bug was found and updated, False otherwise."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")

    bug_path = BUGS_DIR / f"{bug_id}.json"
    if not bug_path.exists():
        return False

    try:
        bug = json.loads(bug_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read bug report {bug_path}: {e}")
        return False

    bug["status"] = status
    bug_path.write_text(json.dumps(bug, indent=2), encoding="utf-8")
    logger.info(f"Updated {bug_id} status to '{status}'")
    return True


def find_bugs_for_test(test_name: str) -> list[str]:
    """Returns the ids of all bugs currently filed against a given test node id."""
    matches = []
    for bug_path in BUGS_DIR.glob("BUG-*.json"):
        try:
            bug = json.loads(bug_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read bug report {bug_path}: {e}")
            continue
        if bug.get("test_name") == test_name:
            matches.append(bug["id"])
    return matches
