"""Reads test data fixtures (JSON/CSV) stored in the test_data directory."""
import csv
import json
from pathlib import Path

TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"


def read_json(file_name: str):
    file_path = TEST_DATA_DIR / file_name
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_csv(file_name: str):
    file_path = TEST_DATA_DIR / file_name
    with open(file_path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
