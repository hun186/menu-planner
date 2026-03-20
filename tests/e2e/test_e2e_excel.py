import json
import urllib.request
import io
import openpyxl
from collections import Counter

BASE = "http://127.0.0.1:18000"


def req(method, path, payload=None):
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)

    with urllib.request.urlopen(r, timeout=180) as f:
        return f.status, dict(f.headers), f.read()


def test_generate_and_export_excel():
    # 取得預設設定
    st, _, body = req("GET", "/config/default")
    assert st == 200

    cfg = json.loads(body)
    cfg["horizon_days"] = 270
    # 使用固定 seed + 關閉 local search，避免隨機鄰域替換造成 CI 偶發失敗
    cfg["seed"] = 7
    (cfg.setdefault("search", {}).setdefault("local_search", {}))["enabled"] = False

    # 生成菜單
    st, _, body = req("POST", "/plan", cfg)
    assert st == 200

    obj = json.loads(body)

    assert obj["ok"] is True
    assert len(obj["result"]["days"]) == 270
    assert obj["result"]["summary"].get("people") == cfg.get("people", 1)

    # 驗證每日組成：1 main + 2 side + 1 veg + 1 soup + 1 fruit
    # 只檢查有排程且成功的日子（offday / failed 另有邏輯）
    days = obj["result"]["days"]
    for d in days:
        if d.get("failed"):
            continue
        items = d.get("items") or {}
        main = items.get("main") or {}
        if not main.get("id"):
            # offday
            continue


        procurement = d.get("procurement") or {}
        assert procurement.get("people") == cfg.get("people", 1)
        sides = items.get("sides") or []
        veg = items.get("veg") or {}
        soup = items.get("soup") or {}
        fruit = items.get("fruit") or {}

        assert len(sides) == 2
        assert all((s or {}).get("id") for s in sides)
        assert veg.get("id")
        assert soup.get("id")
        assert fruit.get("id")

    # 驗證 veg 重複規則（最近 7 個有排餐日）
    rep = (cfg.get("hard") or {}).get("repeat_limits") or {}
    max_veg_7 = int(rep.get("max_same_veg_in_7_days", rep.get("max_same_side_in_7_days", 1)))
    active_completed: list[dict] = []
    for d in days:
        if d.get("failed"):
            continue
        items = d.get("items") or {}
        main_id = ((items.get("main") or {}).get("id") or "").strip()
        veg_id = ((items.get("veg") or {}).get("id") or "").strip()
        if not main_id:
            # offday
            continue
        assert veg_id

        recent_veg_ids = [
            ((x.get("items") or {}).get("veg") or {}).get("id")
            for x in active_completed[-7:]
            if ((x.get("items") or {}).get("veg") or {}).get("id")
        ]
        c = Counter(recent_veg_ids)
        assert c.get(veg_id, 0) + 1 <= max_veg_7
        active_completed.append(d)

    # 匯出 Excel
    st, _, xb = req(
        "POST",
        "/export/excel",
        {
            "cfg": cfg,
            "result": obj["result"],
        },
    )

    assert st == 200

    # 檢查 Excel
    wb = openpyxl.load_workbook(io.BytesIO(xb), data_only=True)

    sheet = wb["菜單"]
    detail_sheet = wb["採買明細"]

    assert sheet.max_row == 271
    assert detail_sheet.max_row > 1
