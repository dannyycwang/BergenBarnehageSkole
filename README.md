# UDIR Grunnskole CSV pipeline (Python)

這個專案把你要的流程拆成 3 個 Python 腳本：

1. 抓 `statistikk-grunnskole` 頁面能下載的 CSV（盡量自動選 `Bergen`）。
2. 合併所有 CSV 成一張表。
3. 做 Bergen 學校地圖。

## 安裝

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
python -m playwright install chromium
```

## 1) 下載 CSV

```bash
python scripts/download_udir_csv.py
```

檔案會放在 `data/raw/`。

## 2) Merge 成一張表 + unique id 註記

```bash
python scripts/merge_csvs.py
```

輸出：
- `data/processed/all_merged.csv`
- `data/processed/id_notes.md`

`id_notes.md` 會列出：
- 哪些 CSV 沒明確學校型 unique key
- 哪些 CSV 是用其他 key（不是學校名）

## 3) 畫 Bergen 地圖

```bash
python scripts/map_bergen.py
```

輸出：
- `outputs/bergen_school_map.html`
- `outputs/bergen_school_points.csv`

## 說明

- 若 UDIR 某些 CSV 需要前端互動參數，`download_udir_csv.py` 會優先嘗試把地區切到 Bergen 再下載。
- 若網站結構改動（按鈕文字或 aria 標記改名），可能需要微調 `scripts/download_udir_csv.py` 的 selector。
