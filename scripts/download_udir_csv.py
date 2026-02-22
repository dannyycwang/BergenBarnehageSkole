#!/usr/bin/env python3
"""Download UDIR CSV by direct click flow: Eksporter -> CSV.

This keeps the interaction simple and close to manual behavior.
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


def click_export_then_csv_and_download(page, output_dir: Path, source_url: str) -> tuple[bool, str | None, str | None]:
    """Return (ok, filename, error)."""
    try:
        export_btn = page.get_by_text(re.compile(r"^\s*Eksporter\s*$", re.I))
        if export_btn.count() == 0:
            export_btn = page.get_by_role("button", name=re.compile("Eksporter", re.I))
        if export_btn.count() == 0:
            return False, None, "Eksporter control not found"

        export_btn.first.click(timeout=8000)
        page.wait_for_timeout(300)

        csv_option = page.get_by_text(re.compile(r"^\s*CSV\s*$", re.I))
        if csv_option.count() == 0:
            csv_option = page.get_by_role("button", name=re.compile(r"CSV", re.I))
        if csv_option.count() == 0:
            return False, None, "CSV option not found after clicking Eksporter"

        with page.expect_download(timeout=35000) as dl_info:
            csv_option.first.click(timeout=8000)

        dl = dl_info.value
        suggested = dl.suggested_filename or f"{slugify(urlparse(source_url).path)}.csv"
        target = output_dir / suggested
        if target.exists():
            target = output_dir / f"{target.stem}_{slugify(urlparse(source_url).path)}{target.suffix}"
        dl.save_as(str(target))
        return True, target.name, None
    except PlaywrightTimeoutError:
        return False, None, "Timed out waiting for download"
    except Exception as exc:
        return False, None, str(exc)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        page.goto(ROOT_URL, wait_until="networkidle", timeout=90000)
        subpages = discover_subpages(page)

        logs: list[dict] = []
        for url in subpages:
            result = {
                "page": url,
                "downloaded": False,
                "filename": None,
                "error": None,
            }
            page.goto(url, wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2500)
            ok, filename, err = click_export_then_csv_and_download(page, RAW_DIR, url)
            result["downloaded"] = ok
            result["filename"] = filename
            result["error"] = err
            logs.append(result)

        browser.close()

    LOG_PATH.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")

    ok = sum(1 for row in logs if row["downloaded"])
    print(f"Discovered {len(subpages)} subpages")
    print(f"Downloaded {ok} CSV files to {RAW_DIR}")
    print(f"Log written to {LOG_PATH}")


if __name__ == "__main__":
    main()
