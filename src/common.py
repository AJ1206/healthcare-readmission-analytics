"""Shared paths, constants and helpers used by every pipeline script."""
from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
UCI_RAW_DIR = RAW_DIR / "uci_diabetes_130"
PROCESSED_DIR = ROOT / "data" / "processed"
FIG_DIR = ROOT / "outputs" / "figures"
TABLE_DIR = ROOT / "outputs" / "tables"
MODEL_DIR = ROOT / "models"
DASHBOARD_DIR = ROOT / "dashboard"
DOCS_DIR = ROOT / "docs"

RAW_CSV = UCI_RAW_DIR / "diabetic_data.csv"
IDS_MAPPING_CSV = UCI_RAW_DIR / "IDS_mapping.csv"
CLEAN_CSV =PROCESSED_DIR / "diabetes_encounters_clean.csv"
INDEX_COHORT_CSV = PROCESSED_DIR / "diabetes_index_encounters.csv"

RANDOM_STATE = 42

for _d in (RAW_DIR, PROCESSED_DIR, FIG_DIR, TABLE_DIR, MODEL_DIR, DASHBOARD_DIR, DOCS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    return logging.getLogger(name)


def save_json(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
