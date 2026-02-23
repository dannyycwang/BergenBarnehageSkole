#!/usr/bin/env python3
"""Deprecated downloader.

The project now expects manually downloaded CSV files in `E_report/`.
Use `scripts/merge_csvs.py` to combine and format the dataset.
"""

from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "download_udir_csv.py is deprecated. Put your CSV files in E_report/ and run: "
        "python scripts/merge_csvs.py"
    )


if __name__ == "__main__":
    main()
