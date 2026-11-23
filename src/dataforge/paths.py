"""Project directories, defined once and imported everywhere else."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_OUTPUT_DIR = PROJECT_ROOT / "data"
LANDING_DIR = DATA_OUTPUT_DIR / "landing"
FEEDS_DIR = DATA_OUTPUT_DIR / "feeds"
WATERMARK_FILE = DATA_OUTPUT_DIR / "watermark" / "watermark.json"
