"""CLI to (re)build the FAISS + BM25 + metadata indexes from the dataset.

Usage (from the repo root):
    python -m backend.scripts.build_index
    python -m backend.scripts.build_index --dataset data/hospitals.xlsx
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Make sure ``backend`` is importable when running this file directly.
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import ensure_dirs  # noqa: E402
from backend.app.search import SearchEngine  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_index")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CareGrid AI indexes")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="Path to hospitals CSV/XLSX (defaults to data/hospitals.{csv,xlsx})",
    )
    args = parser.parse_args()

    ensure_dirs()
    start = time.time()
    logger.info("Building indexes...")
    engine = SearchEngine.build(args.dataset)
    engine.persist()
    elapsed = time.time() - start
    logger.info("Done. %d rows indexed in %.1fs.", len(engine.df), elapsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
