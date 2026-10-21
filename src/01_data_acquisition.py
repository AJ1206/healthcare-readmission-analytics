"""Step 1 - Data acquisition.

Downloads the UCI "Diabetes 130-US Hospitals for Years 1999-2008" archive,
keeps the untouched ZIP, extracts only the expected CSV files, records a
SHA-256 checksum and provenance metadata, and probes the accessibility of the
alternative datasets considered during dataset selection.
"""
from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DOCS_DIR, RAW_DIR, UCI_RAW_DIR, get_logger, save_json  # noqa: E402

log = get_logger("acquisition")

UCI_ZIP_URL = "https://archive.ics.uci.edu/static/public/296/diabetes+130-us+hospitals+for+years+1999-2008.zip"
UCI_PAGE = "https://archive.ics.uci.edu/dataset/296/diabetes+130-us+hospitals+for+years+1999-2008"
EXPECTED_MEMBERS = {"diabetic_data.csv", "IDS_mapping.csv"}

# Alternative datasets evaluated in the selection matrix. Each is probed so the
# comparison records whether it was actually reachable on the access date.
CANDIDATE_PROBES = {
    "CMS Hospital Readmissions Reduction Program (HRRP)": "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/9n3s-kdb3",
    "CDC Diabetes Health Indicators (BRFSS 2014, via UCI)": "https://archive.ics.uci.edu/dataset/891/cdc+diabetes+health+indicators",
    "MIMIC-IV (PhysioNet, credentialed access)": "https://physionet.org/content/mimiciv/",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str, timeout: int = 120) -> bytes:
    log.info("Downloading %s", url)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def extract_expected(zip_bytes: bytes, dest: Path) -> list[str]:
    """Extract only the known CSV members; refuse unexpected paths (zip-slip safe)."""
    dest.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        log.info("Archive members: %s", names)
        for name in names:
            base = Path(name).name
            if base not in EXPECTED_MEMBERS:
                log.warning("Skipping unexpected member %s", name)
                continue
            (dest / base).write_bytes(zf.read(name))
            extracted.append(base)
    missing = EXPECTED_MEMBERS - set(extracted)
    if missing:
        raise RuntimeError(f"Archive is missing expected files: {missing}")
    return extracted


def probe_candidates() -> list[dict]:
    rows = []
    for name, url in CANDIDATE_PROBES.items():
        try:
            r = requests.get(url, timeout=30)
            status = r.status_code
            note = ""
            if "data.cms.gov" in url and r.ok:
                meta = r.json()
                note = f"title={meta.get('title')}; modified={meta.get('modified')}"
        except requests.RequestException as exc:  # network issues are recorded, not fatal
            status, note = None, f"error: {exc}"
        rows.append({"dataset": name, "probe_url": url, "http_status": status, "note": note})
        log.info("Probe %s -> %s %s", name, status, note)
    return rows


def main() -> None:
    accessed = datetime.now(timezone.utc).isoformat(timespec="seconds")
    zip_bytes = download(UCI_ZIP_URL)
    zip_path = RAW_DIR / "diabetes_130_us_hospitals_1999_2008.zip"
    zip_path.write_bytes(zip_bytes)  # untouched original archive
    files = extract_expected(zip_bytes, UCI_RAW_DIR)

    metadata = {
        "dataset_title": "Diabetes 130-US Hospitals for Years 1999-2008",
        "publisher": "UCI Machine Learning Repository",
        "creators": "Clore, J., Cios, K., DeShazo, J., & Strack, B. (2014)",
        "doi": "https://doi.org/10.24432/C5230J",
        "landing_page": UCI_PAGE,
        "download_url": UCI_ZIP_URL,
        "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
        "accessed_utc": accessed,
        "archive_sha256": sha256(zip_bytes),
        "archive_bytes": len(zip_bytes),
        "files": {f: {"sha256": sha256((UCI_RAW_DIR / f).read_bytes()),
                      "bytes": (UCI_RAW_DIR / f).stat().st_size} for f in files},
        "introductory_paper": "Strack, B., et al. (2014). Impact of HbA1c measurement on hospital readmission "
                              "rates: Analysis of 70,000 clinical database patient records. BioMed Research "
                              "International, 2014, 781670.",
    }
    save_json(metadata, RAW_DIR / "SOURCE_METADATA.json")
    save_json({"accessed_utc": accessed, "probes": probe_candidates()}, DOCS_DIR / "dataset_access_probes.json")
    log.info("Acquisition complete: %s", metadata["files"])


if __name__ == "__main__":
    main()
