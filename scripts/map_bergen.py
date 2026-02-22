#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import pandas as pd
import folium
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

INPUT = Path("data/processed/all_merged.csv")
OUT = Path("outputs/bergen_school_map.html")


def find_first(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        for lc, orig in lower.items():
            if cand in lc:
                return orig
    return None


def main() -> None:
    if not INPUT.exists():
        raise SystemExit("Missing merged file. Run scripts/merge_csvs.py first.")

    df = pd.read_csv(INPUT)

    school_col = find_first(df, ["skole", "school"])
    kommune_col = find_first(df, ["kommune", "municipality"])

    if school_col is None:
        raise SystemExit("No school name column found in merged data.")

    work = df.copy()
    if kommune_col:
        work = work[work[kommune_col].astype(str).str.contains("bergen", case=False, na=False)]

    work = work[[school_col]].dropna().drop_duplicates().reset_index(drop=True)

    geolocator = Nominatim(user_agent="bergen_school_mapper")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    lats, lons = [], []
    for school in work[school_col].astype(str):
        query = f"{school}, Bergen, Norway"
        loc = geocode(query)
        if loc:
            lats.append(loc.latitude)
            lons.append(loc.longitude)
        else:
            lats.append(None)
            lons.append(None)

    work["lat"] = lats
    work["lon"] = lons
    mappable = work.dropna(subset=["lat", "lon"]) 

    center = [60.39299, 5.32415]
    if not mappable.empty:
        center = [mappable["lat"].mean(), mappable["lon"].mean()]

    fmap = folium.Map(location=center, zoom_start=11)
    for _, row in mappable.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4,
            popup=str(row[school_col]),
            color="blue",
            fill=True,
        ).add_to(fmap)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(OUT))

    points_out = Path("outputs/bergen_school_points.csv")
    work.to_csv(points_out, index=False)

    print(f"Map saved to {OUT}")
    print(f"Geocoded points saved to {points_out}")


if __name__ == "__main__":
    main()
