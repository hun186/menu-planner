# Admin 成本警示 Tooltip 截圖驗證（2026-03-20）

## 測試檔
- `scripts/validation/playwright_admin_cost_tooltip.py`

## 產生截圖指令
```bash
python scripts/validation/playwright_admin_cost_tooltip.py
```

## 執行結果
- 目前環境缺少 `playwright` 套件，且外部套件安裝被代理 403 阻擋，無法在此環境完成瀏覽器自動化與產圖。
- 因此 `artifacts/admin-cost-tooltip.png` 在本次提交中尚未成功生成。

## 相關錯誤輸出（摘要）
```text
ModuleNotFoundError: No module named 'playwright'
ERROR: No matching distribution found for playwright
```
