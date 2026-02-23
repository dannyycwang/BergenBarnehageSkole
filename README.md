# UDIR Grunnskole CSV pipeline (Python)

已改成**手動下載 CSV** 的流程：

1. 把你自己抓好的 CSV 全部放到 `E_report/`。
2. 執行 merge 腳本，自動清理欄位名稱、合併、排序。
3. 輸出整齊可讀的 CSV + Excel（含表頭樣式、凍結首列、自動欄寬）。
4. （可選）再用合併結果畫 Bergen 學校地圖。

## 安裝

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## 1) 放入資料

把所有來源 CSV 放到（可放子資料夾，會遞迴掃描）：

```text
E_report/
```

## 2) Merge 成一張表（整齊版）

```bash
python scripts/merge_csvs.py
```

輸出：
- `data/processed/all_merged.csv`
- `data/processed/all_merged.xlsx`（格式化表格，方便閱讀）
- `data/processed/merge_report.md`

## 3) 畫 Bergen 地圖（可選）

```bash
python scripts/map_bergen.py
```

輸出：
- `outputs/bergen_school_map.html`
- `outputs/bergen_school_points.csv`

## 備註

- `scripts/download_udir_csv.py` 已停用（deprecated）。
- 若沒有輸入檔，`merge_csvs.py` 會提示你先放 CSV 到 `E_report/`。
