"""Self-healing, self-learning locator resolution.

Instead of a single hard-coded selector, an element is described by a list of candidate
selectors. SmartLocator tries them in order of past success (persisted in
test_data/locator_repository.json), "heals" onto whichever candidate is currently visible,
and reinforces/decays scores over time so the repository keeps learning which selector is
most reliable for a given element.
"""
import json
from pathlib import Path

from playwright.sync_api import Locator, Page

from utils.logger import get_logger

logger = get_logger(__name__)

REPO_PATH = Path(__file__).parent.parent / "test_data" / "locator_repository.json"


def _load_repo() -> dict:
    if REPO_PATH.exists():
        with open(REPO_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_repo(repo: dict):
    REPO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPO_PATH, "w", encoding="utf-8") as f:
        json.dump(repo, f, indent=2)


class SmartLocator:
    """Resolves an element via a ranked list of candidate selectors, healing to the next one on failure."""

    def __init__(self, page: Page, key: str, candidates: list[str], timeout: int = 3000):
        self.page = page
        self.key = key
        self.candidates = candidates
        self.timeout = timeout

    def resolve(self) -> Locator:
        repo = _load_repo()
        entry = repo.get(self.key, {"strategies": [], "scores": {}})
        # Merge in candidates newly added/edited in code so a repo cached from a previous run
        # never masks a locator change the developer just made.
        for candidate in self.candidates:
            if candidate not in entry["strategies"]:
                entry["strategies"].append(candidate)
            entry["scores"].setdefault(candidate, 1)

        ordered = sorted(entry["strategies"], key=lambda c: entry["scores"].get(c, 1), reverse=True)

        last_error = None
        for selector in ordered:
            locator = self.page.locator(selector)
            try:
                locator.wait_for(state="visible", timeout=self.timeout)
                entry["scores"][selector] = entry["scores"].get(selector, 1) + 1
                if selector != ordered[0]:
                    logger.warning(f"Self-healed locator '{self.key}': switched to selector '{selector}'")
                repo[self.key] = entry
                _save_repo(repo)
                return locator
            except Exception as e:
                entry["scores"][selector] = max(entry["scores"].get(selector, 1) - 1, 0)
                last_error = e
                continue

        repo[self.key] = entry
        _save_repo(repo)
        raise last_error or Exception(f"No candidate selector resolved for '{self.key}': {self.candidates}")


def prune_stale_entries(min_score: int = 0):
    """Drops candidate selectors that have decayed to/below min_score, keeping the repository lean over time."""
    repo = _load_repo()
    for key, entry in list(repo.items()):
        entry["strategies"] = [s for s in entry["strategies"] if entry["scores"].get(s, 1) > min_score]
        if not entry["strategies"]:
            del repo[key]
    _save_repo(repo)
