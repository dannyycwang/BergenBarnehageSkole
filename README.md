# UDIR Grunnskole CSV pipeline (Python)

這個專案把你要的流程拆成 3 個 Python 腳本：

1. 先從 `statistikk-grunnskole` 首頁抓所有子統計頁，再逐頁按 `Eksporter` 下載 CSV。每頁只嘗試在 `Enhet` 設成 `Vestland/Bergen`，其他維持預設。
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

檔案會放在 `data/raw/`，並輸出 `data/raw/download_log.json`，記錄每頁是否成功套用 `Enhet=Vestland/Bergen`；若該頁沒有此選項，會回退成預設（全部）下載。

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

- `download_udir_csv.py` 目前固定策略：只改 `Enhet=Vestland/Bergen`，其餘條件維持預設。
- 若網站結構改動（按鈕文字或 aria 標記改名），可能需要微調 `scripts/download_udir_csv.py` 的 selector。
