#!/usr/bin/env bash
# iconCut 打包脚本 (macOS / Linux) - 单文件便携版(含图标)
# 用法: chmod +x build.sh && ./build.sh
set -e

PY_EXE=$(command -v python3 || command -v python)
if [ -z "$PY_EXE" ]; then
    echo "[错误] 未找到 Python,请安装 Python 3.11-3.13。"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[iconCut] 使用 Python: $PY_EXE"

echo "[iconCut] 安装 PyInstaller + Pillow(图标生成)..."
"$PY_EXE" -m pip install pyinstaller Pillow

echo "[iconCut] 生成图标 (ICO / ICNS)..."
"$PY_EXE" tools/make_icons.py

ICON_DIR="$SCRIPT_DIR/图标"
ICNS="$ICON_DIR/MMY-AI-Studio-icon.icns"
ICO="$ICON_DIR/MMY-AI-Studio-icon.ico"

# 按平台选择图标文件
ICON_FILE=""
case "$(uname -s)" in
    Darwin*)  [ -f "$ICNS" ] && ICON_FILE="$ICNS" ;;          # macOS: .icns
    MINGW*|CYGWIN*|MSYS*) [ -f "$ICO" ] && ICON_FILE="$ICO" ;; # Windows(msys): .ico
    *)  ICON_FILE="" ;;                                        # Linux: 二进制不带图标
esac

# 清理旧产物
rm -rf "$SCRIPT_DIR/dist/iconCut.app" "$SCRIPT_DIR/dist/iconCut"

ICON_ARG=""
if [ -n "$ICON_FILE" ] && [ -f "$ICON_FILE" ]; then
    ICON_ARG="--icon $ICON_FILE"
fi

echo "[iconCut] 开始打包 (--onefile --windowed)..."
"$PY_EXE" -m PyInstaller --onefile --windowed --name iconCut $ICON_ARG \
    --add-data "图标:图标" \
    main.py

echo ""
echo "[iconCut] 打包完成!"
if [ -d "$SCRIPT_DIR/dist/iconCut.app" ]; then
    echo "  macOS 便携包: dist/iconCut.app  (可直接拷贝到其他 Mac 运行)"
    echo "  终端运行: dist/iconCut.app/Contents/MacOS/iconCut"
else
    echo "  产物: dist/iconCut"
fi
