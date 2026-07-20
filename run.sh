#!/usr/bin/env bash
# iconCut 启动脚本 (macOS / Linux)
set -e
PY_EXE=$(command -v python3 || command -v python)

if [ -z "$PY_EXE" ]; then
    echo "[错误] 未找到 Python。请安装 Python 3.11-3.13。"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[iconCut] 使用 Python: $PY_EXE"

# 自动安装缺失依赖
"$PY_EXE" -c "import PySide6, cv2, numpy, PIL" 2>/dev/null || {
    echo "[iconCut] 首次运行,正在安装依赖..."
    "$PY_EXE" -m pip install -r requirements.txt
}

"$PY_EXE" main.py
