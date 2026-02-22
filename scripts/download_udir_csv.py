#!/usr/bin/env python3
"""Download CSV exports from UDIR grunnskole statistics pages.

Workflow aligned with user request:
- Open each `statistikk-grunnskole` subpage.
- Keep defaults, only set Enhet to Vestland/Bergen when available.
- Click Eksporter and save CSV.
- If Enhet filter cannot be set on a page, export with default/all selection.
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


ENHET_LABEL_RE = re.compile(r"enhet", re.I)
VESTLAND_RE = re.compile(r"vestland", re.I)
BERGEN_RE = re.compile(r"bergen", re.I)


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


def click_first(locator, timeout=1500) -> bool:
    try:
        if locator.count() > 0:
            locator.first.click(timeout=timeout)
            return True
    except Exception:
        return False
    return False


def open_enhet_control(page) -> bool:
    """Open the Enhet filter control (combobox/button/select) if present."""
    # First try by associated label text around control
    candidates = page.locator("[role='combobox'], button[aria-haspopup='listbox'], select")
    for i in range(candidates.count()):
        c = candidates.nth(i)
        blob = ""
        try:
            blob += (c.inner_text(timeout=300) or "") + " "
        except Exception:
            pass
        try:
            blob += (c.get_attribute("aria-label") or "") + " "
        except Exception:
            pass
        try:
            blob += (c.get_attribute("name") or "") + " "
        except Exception:
            pass
        if ENHET_LABEL_RE.search(blob):
            try:
                c.click(timeout=1500)
                return True
            except Exception:
                continue

    # Fallback: click visible "Enhet" text near filter panel
    if click_first(page.get_by_text(ENHET_LABEL_RE), timeout=1200):
        return True

    return False


def select_enhet_vestland_bergen(page) -> tuple[bool, str]:
    """Try setting Enhet filter to Vestland/Bergen.

    Returns: (selected, detail)
    """
    # Case 1: direct composite option
    if open_enhet_control(page):
        if click_first(page.get_by_role("option", name=re.compile(r"vestland\s*/\s*bergen", re.I))):
            return True, "selected via option Vestland/Bergen"
        if click_first(page.get_by_text(re.compile(r"vestland\s*/\s*bergen", re.I))):
            return True, "selected via text Vestland/Bergen"

    # Case 2: two-step hierarchy Vestland -> Bergen
    if open_enhet_control(page):
        if click_first(page.get_by_role("option", name=VESTLAND_RE)) or click_first(page.get_by_text(VESTLAND_RE)):
            page.wait_for_timeout(300)
            if click_first(page.get_by_role("option", name=BERGEN_RE)) or click_first(page.get_by_text(BERGEN_RE)):
                return True, "selected via hierarchy Vestland -> Bergen"

    # Case 3: any Bergen option once Enhet opened
    if open_enhet_control(page):
        if click_first(page.get_by_role("option", name=BERGEN_RE)) or click_first(page.get_by_text(BERGEN_RE)):
            return True, "selected Bergen under Enhet"

    return False, "Enhet Vestland/Bergen not available on this page"


def ensure_csv_selected(page) -> None:
    try:
        csv_text = page.get_by_text(re.compile(r"\bCSV\b", re.I))
        if csv_text.count() > 0:
            csv_text.first.click(timeout=1000)
            return
    except Exception:
        pass

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
        "enhet_vestland_bergen_selected": False,
        "selection_detail": None,
        "fallback_to_default_selection": False,
        "error": None,
    }

    page.goto(url, wait_until="networkidle", timeout=90000)
    page.wait_for_timeout(4500)

    selected, detail = select_enhet_vestland_bergen(page)
    result["enhet_vestland_bergen_selected"] = selected
    result["selection_detail"] = detail
    if not selected:
        result["fallback_to_default_selection"] = True

    ensure_csv_selected(page)

    exporter = page.get_by_role("button", name=re.compile(r"Eksporter", re.I))
    if exporter.count() == 0:
        exporter = page.get_by_text(re.compile(r"Eksporter", re.I))

    if exporter.count() == 0:
        result["error"] = "Eksporter control not found"
        return result

    try:
        with page.expect_download(timeout=35000) as download_info:
            exporter.first.click(timeout=6000)
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
    scoped = sum(1 for item in logs if item["enhet_vestland_bergen_selected"])
    print(f"Discovered {len(subpages)} subpages")
    print(f"Downloaded {ok} CSV files to {RAW_DIR}")
    print(f"Applied Enhet Vestland/Bergen on {scoped} pages")
    print(f"Log written to {LOG_PATH}")


if __name__ == "__main__":
    main()
