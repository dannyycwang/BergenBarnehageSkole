#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/processed")
REPORT = OUT_DIR / "id_notes.md"

ID_HINTS = ["skole", "school", "school_name", "enhetsnummer", "orgnr", "unit", "id"]


def read_csv_flexible(path: Path) -> pd.DataFrame:
    for sep in [",", ";", "\t"]:
        try:
            df = pd.read_csv(path, sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    return pd.read_csv(path)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    df = df.copy()
    df.columns = cols
    return df


def pick_id_column(df: pd.DataFrame) -> str | None:
    for col in df.columns:
        c = col.lower()
        if any(h in c for h in ID_HINTS):
            return col
    return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW_DIR.glob("*.csv"))

    if not files:
        raise SystemExit("No CSV files found in data/raw. Run download_udir_csv.py first.")

    frames = []
    notes = []

    for f in files:
        df = normalize_columns(read_csv_flexible(f))
        id_col = pick_id_column(df)

        if id_col is None:
            notes.append(f"- `{f.name}`: no clear school-style unique ID column found.")
        elif "skole" not in id_col and "school" not in id_col:
            notes.append(f"- `{f.name}`: unique key seems to be `{id_col}` (not school name).")

        df["source_file"] = f.name
        frames.append((f.name, df, id_col))

    merged = None
    merge_key = None

    for _, df, id_col in frames:
        if merged is None:
            merged = df
            merge_key = id_col
            continue

        if merge_key and merge_key in df.columns:
            key = merge_key
        elif id_col and id_col in merged.columns and id_col in df.columns:
            key = id_col
            merge_key = key
        else:
            common = [c for c in merged.columns if c in df.columns and c != "source_file"]
            key = common[0] if common else None

        if key:
            merged = merged.merge(df, on=key, how="outer", suffixes=("", "_dup"))
        else:
            merged = pd.concat([merged, df], ignore_index=True, sort=False)

    merged_out = OUT_DIR / "all_merged.csv"
    merged.to_csv(merged_out, index=False)

    REPORT.write_text(
        "# Unique ID notes\n\n"
        + ("\n".join(notes) if notes else "- All files appear to use a school-related key column.")
        + "\n",
        encoding="utf-8",
    )

    print(f"Merged CSV saved to: {merged_out}")
    print(f"ID note report saved to: {REPORT}")


if __name__ == "__main__":
    main()
