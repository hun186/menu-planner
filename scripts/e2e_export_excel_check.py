from __future__ import annotations

import io
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import suppress

import openpyxl

HOST = "127.0.0.1"
PORT = 18000
BASE = f"http://{HOST}:{PORT}"


def _request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict, bytes]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.status, dict(resp.headers), resp.read()


def _wait_server(timeout_s: float = 30.0) -> None:
    started = time.time()
    while time.time() - started < timeout_s:
        with suppress(Exception):
            status, _, _ = _request("GET", "/config/default")
            if status == 200:
                return
        time.sleep(0.5)
    raise RuntimeError("Server did not become ready in time")


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.menu_planner.api.main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        _wait_server()

        _, _, default_body = _request("GET", "/config/default")
        cfg = json.loads(default_body)
        cfg["horizon_days"] = 270

        status, _, plan_body = _request("POST", "/plan", cfg)
        if status != 200:
            raise RuntimeError(f"/plan failed: status={status}")
        plan_payload = json.loads(plan_body)
        if not plan_payload.get("ok"):
            raise RuntimeError(f"/plan returned not ok: {plan_payload}")

        result = plan_payload["result"]
        if len(result.get("days", [])) != 270:
            raise RuntimeError(f"Expected 270 days, got {len(result.get('days', []))}")

        status, _, excel_body = _request("POST", "/export/excel", {"cfg": cfg, "result": result})
        if status != 200:
            raise RuntimeError(f"/export/excel failed: status={status}")

        wb = openpyxl.load_workbook(io.BytesIO(excel_body), data_only=True)
        menu_rows = wb["菜單"].max_row
        if menu_rows != 271:
            raise RuntimeError(f"Expected 菜單 rows=271 (含標題), got {menu_rows}")

        print(
            json.dumps(
                {
                    "plan_days": len(result.get("days", [])),
                    "excel_bytes": len(excel_body),
                    "menu_sheet_rows": menu_rows,
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        proc.terminate()
        with suppress(Exception):
            proc.wait(timeout=10)
        if proc.poll() is None:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
