import json
import urllib.request
import io
import openpyxl

BASE = "http://127.0.0.1:8000"


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

    # 生成菜單
    st, _, body = req("POST", "/plan", cfg)
    assert st == 200

    obj = json.loads(body)

    assert obj["ok"] is True
    assert len(obj["result"]["days"]) == 270

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

    assert sheet.max_row == 271