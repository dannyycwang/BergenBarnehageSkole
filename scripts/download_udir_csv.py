#!/usr/bin/env python3
"""Download CSV exports from UDIR grunnskole statistics pages.

Improvement over the previous version:
- First discovers the detailed statistic subpages from the main overview page.
- Visits each subpage and clicks its `Eksporter` action (CSV export in Statistikportalen UI).
- Best-effort Bergen filter selection before export when such controls are present.
- Saves metadata log so failures are visible instead of silently skipping.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.udir.no"
ROOT_URL = f"{BASE_URL}/tall-og-forskning/statistikk/statistikk-grunnskole/"
RAW_DIR = Path("data/raw")
LOG_PATH = RAW_DIR / "download_log.json"


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", value).strip("_").lower()


def is_grunnskole_subpage(href: str) -> bool:
    if not href:
        return False
    parsed = urlparse(href)
    path = parsed.path.rstrip("/")
    root = "/tall-og-forskning/statistikk/statistikk-grunnskole"
    return path.startswith(root) and path != root


def discover_subpages(page) -> list[str]:
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    urls = []
    for href in hrefs:
        if not href:
            continue
        full = urljoin(BASE_URL, href)
        if is_grunnskole_subpage(full):
            urls.append(full.rstrip("/") + "/")
    return sorted(set(urls))


def try_set_bergen(page) -> bool:
    """Try multiple control styles used by Statistikportalen to select Bergen."""
    # 1) direct option click if visible
    try:
        opt = page.get_by_text(re.compile(r"^Bergen$", re.I))
        if opt.count() > 0:
            opt.first.click(timeout=1500)
            return True
    except Exception:
        pass

    # 2) combobox style controls
    combos = page.locator("[role='combobox'], select, button[aria-haspopup='listbox']")
    for i in range(combos.count()):
        c = combos.nth(i)
        try:
            c.click(timeout=1500)
        except Exception:
            continue

        # try listbox option
        try:
            opt = page.get_by_role("option", name=re.compile("bergen", re.I))
            if opt.count() > 0:
                opt.first.click(timeout=1500)
                return True
        except Exception:
            pass

        # try plain text option in dropdown
        try:
            txt = page.get_by_text(re.compile(r"\bBergen\b", re.I))
            if txt.count() > 0:
                txt.first.click(timeout=1500)
                return True
        except Exception:
            pass

    return False


def ensure_csv_selected(page) -> None:
    """Best-effort: ensure export format is CSV before clicking Eksporter."""
    # common pattern: "Filtype" followed by CSV option/button
    try:
        csv_text = page.get_by_text(re.compile(r"\bCSV\b", re.I))
        if csv_text.count() > 0:
            csv_text.first.click(timeout=1000)
            return
    except Exception:
        pass

    # select tag fallback
    selects = page.locator("select")
    for i in range(selects.count()):
        s = selects.nth(i)
        try:
            s.select_option(label=re.compile("csv", re.I), timeout=1000)
            return
        except Exception:
            continue


def download_page_csv(page, url: str, raw_dir: Path) -> dict:
    result = {
        "page": url,
        "downloaded": False,
        "filename": None,
        "bergen_selected": False,
        "error": None,
    }

    page.goto(url, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(4000)

    result["bergen_selected"] = try_set_bergen(page)
    ensure_csv_selected(page)

    # some pages use button, others link styled as button
    exporter = page.get_by_role("button", name=re.compile(r"Eksporter", re.I))
    if exporter.count() == 0:
        exporter = page.get_by_text(re.compile(r"Eksporter", re.I))

    if exporter.count() == 0:
        result["error"] = "Eksporter control not found"
        return result

    try:
        with page.expect_download(timeout=25000) as download_info:
            exporter.first.click(timeout=5000)
        dl = download_info.value
        suggested = dl.suggested_filename or f"{slugify(urlparse(url).path)}.csv"
        target = raw_dir / suggested
        if target.exists():
            target = raw_dir / f"{target.stem}_{slugify(urlparse(url).path)}{target.suffix}"
        dl.save_as(str(target))
        result["downloaded"] = True
        result["filename"] = target.name
    except PlaywrightTimeoutError:
        result["error"] = "Timed out waiting for download"
    except Exception as exc:
        result["error"] = str(exc)

    return result


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto(ROOT_URL, wait_until="networkidle", timeout=90000)
        subpages = discover_subpages(page)

        logs = []
        for url in subpages:
            logs.append(download_page_csv(page, url, RAW_DIR))

        browser.close()

    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for item in logs if item["downloaded"])
    print(f"Discovered {len(subpages)} subpages")
    print(f"Downloaded {ok} CSV files to {RAW_DIR}")
    print(f"Log written to {LOG_PATH}")


if __name__ == "__main__":
    main()
