#!/usr/bin/env python3
"""Use Playwright to download all visible CSV files from UDIR grunnskole page.

Notes:
- Tries to set region filter to Bergen where region controls exist.
- Clicks all buttons/links that contain "CSV" text.
- Saves files under data/raw.
"""

from __future__ import annotations

import re
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://www.udir.no/tall-og-forskning/statistikk/statistikk-grunnskole/"
RAW_DIR = Path("data/raw")

SECTION_TEXTS = [
    "Fakta",
    "Resultater",
    "Trivsel og overganger",
    "Vis mindre",
    "Vis færre",
]


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()


def try_set_bergen(page) -> None:
    """Attempt to set any Region/Kommune/Area selectors to Bergen."""
    candidates = [
        "select",
        "[role='combobox']",
        "button[aria-haspopup='listbox']",
    ]

    for selector in candidates:
        elements = page.locator(selector)
        count = elements.count()
        for i in range(count):
            el = elements.nth(i)
            try:
                label = (el.inner_text(timeout=2000) or "").lower()
            except Exception:
                label = ""
            try:
                aria = (el.get_attribute("aria-label") or "").lower()
            except Exception:
                aria = ""
            merged = f"{label} {aria}"
            if any(x in merged for x in ["region", "kommune", "area", "fylke", "geografi"]):
                try:
                    if selector == "select":
                        el.select_option(label=re.compile("bergen", re.I), timeout=3000)
                    else:
                        el.click(timeout=3000)
                        page.get_by_role("option", name=re.compile("bergen", re.I)).first.click(timeout=3000)
                    print("[info] Set filter to Bergen")
                except Exception:
                    pass


def click_text_if_exists(page, text: str) -> None:
    loc = page.get_by_text(text, exact=False)
    if loc.count() > 0:
        try:
            loc.first.click(timeout=3000)
        except Exception:
            pass


def download_all_csv(page, raw_dir: Path) -> list[Path]:
    downloaded: list[Path] = []
    buttons = page.locator("a,button")
    seen = set()

    for i in range(buttons.count()):
        btn = buttons.nth(i)
        text = (btn.inner_text(timeout=2000) or "").strip()
        if "csv" not in text.lower():
            continue

        key = slugify(text) + f"_{i}"
        if key in seen:
            continue
        seen.add(key)

        try:
            with page.expect_download(timeout=15000) as download_info:
                btn.click(timeout=4000)
            dl = download_info.value
            name = dl.suggested_filename or f"{key}.csv"
            target = raw_dir / name
            if target.exists():
                target = raw_dir / f"{target.stem}_{i}{target.suffix}"
            dl.save_as(str(target))
            downloaded.append(target)
            print(f"[ok] downloaded {target}")
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    return downloaded


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60000)

        for section in SECTION_TEXTS:
            click_text_if_exists(page, section)

        try_set_bergen(page)
        files = download_all_csv(page, RAW_DIR)

        browser.close()

    print(f"Downloaded {len(files)} CSV files into {RAW_DIR}")


if __name__ == "__main__":
    main()
