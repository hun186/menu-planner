#!/usr/bin/env bash
set -euo pipefail

API_PID=""

pick_python() {
  local candidates=()
  if [[ -n "${MENU_PLANNER_PYTHON:-}" ]]; then
    candidates+=("$MENU_PLANNER_PYTHON")
  fi
  candidates+=(
    "$PWD/.venv/bin/python"
    "$HOME/.pyenv/versions/3.10.19/bin/python"
    "python"
    "python3"
  )

  for py in "${candidates[@]}"; do
    if command -v "$py" >/dev/null 2>&1; then
      if "$py" -c "import uvicorn, pytest" >/dev/null 2>&1; then
        echo "$py"
        return 0
      fi
    fi
  done

  echo "找不到可用 Python（需同時安裝 uvicorn 與 pytest）。" >&2
  echo "可先設定 MENU_PLANNER_PYTHON=/path/to/python" >&2
  return 1
}

run_api() {
  local py="$1"
  shift
  exec "$py" -m uvicorn src.menu_planner.api.main:app --host 127.0.0.1 --port 18000 "$@"
}

run_pytest() {
  local py="$1"
  shift
  exec "$py" -m pytest "$@"
}

run_api_and_pytest() {
  local py="$1"
  shift

  "$py" -m uvicorn src.menu_planner.api.main:app --host 127.0.0.1 --port 18000 >/tmp/menu_planner_api.log 2>&1 &
  API_PID=$!

  cleanup() {
    if [[ -n "$API_PID" ]]; then
      kill "$API_PID" >/dev/null 2>&1 || true
    fi
  }
  trap cleanup EXIT

  sleep 2
  "$py" -m pytest "$@"
}

main() {
  local cmd="${1:-}"
  if [[ -z "$cmd" ]]; then
    echo "用法: scripts/dev/dev_env.sh [python|api|pytest|api-test] [args...]" >&2
    exit 1
  fi
  shift

  local py
  py="$(pick_python)"

  case "$cmd" in
    python)
      echo "$py"
      ;;
    api)
      run_api "$py" "$@"
      ;;
    pytest)
      run_pytest "$py" "$@"
      ;;
    api-test)
      run_api_and_pytest "$py" "$@"
      ;;
    *)
      echo "未知指令: $cmd" >&2
      exit 1
      ;;
  esac
}

main "$@"
