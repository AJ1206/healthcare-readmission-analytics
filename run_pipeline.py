"""Run the full analysis pipeline in order: python run_pipeline.py [--from N]

Each step is a separate script so it can also be run on its own.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
STEPS = ["01_data_acquisition.py", "02_data_quality_and_cleaning.py", "03_exploratory_data_analysis.py",
         "04_statistical_analysis.py", "05_predictive_modeling.py", "06_visualization_dashboard.py",
         "07_build_report.py", "08_build_weekly_reports.py", "09_build_project_review_pdf.py"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1, help="step number to start from (1-7)")
    args = ap.parse_args()
    for step in STEPS[args.start - 1:]:
        t0 = time.time()
        print(f"\n=== {step} ===", flush=True)
        result = subprocess.run([sys.executable, str(SRC / step)])
        if result.returncode != 0:
            sys.exit(f"{step} failed with exit code {result.returncode}")
        print(f"=== {step} finished in {time.time() - t0:.0f}s ===", flush=True)
    print("\nPipeline complete. On Windows with Microsoft Word, refresh the report's table of contents with:\n"
          "  powershell -ExecutionPolicy Bypass -File src/update_word_fields.ps1 "
          "-Docx <full path to report/Healthcare_Data_Analytics_Final_Report.docx>\n"
          "Otherwise open the report in Word and press Ctrl+A, then F9.")


if __name__ == "__main__":
    main()
