# MMY iconCut · Go+Fyne 原型

用 **Go + Fyne** 重写的图标抠色工具最小可跑原型，用于验证：能否把单文件 exe 体积从
PyInstaller + PySide6 的 **~107 MB** 大幅压小（目标 10–30 MB 量级），同时保留跨平台单文件能力。

## 功能（与原 Python 版对齐）
- 加载带背景的图标 PNG（RGBA）
- **吸管 eyedropper**：点击吸取颜色，按容差做全图颜色匹配抠色
- **魔棒 wand**：从种子点 flood fill 选中连通区域（类似 PS 魔棒）
- **笔刷 brush**：按住拖动涂抹保护区域（右键/擦除模式可擦除）
- 容差 / 羽化 / 笔刷大小 滑块
- 三种预览：**原图 / 结果(棋盘格) / Alpha 蒙版**
- 导出带透明通道的 PNG

## 目录
```
go-fyne-iconcut/
├── go.mod
├── main.go          # 入口
├── processor.go     # 纯 Go 图像处理(吸色/魔棒/笔刷/alpha 合成/导出)
├── ui.go            # Fyne 界面 + 自绘 PixCanvas(坐标映射)
├── build-go.bat     # Windows 一键构建
├── build-go.sh      # macOS / Linux 一键构建
└── README.md
```

## 构建前提
Fyne 依赖 **CGO**，需要：
- [Go](https://go.dev/dl/) 1.23+
- C 编译器：Windows 用 [winlibs MinGW-w64 UCRT64](https://github.com/brechtsanders/winlibs-mingw-w64)（把 `bin/` 加入 PATH）；macOS/Linux 用系统 `gcc`/`clang`

## 构建与运行
```bash
# Windows
build-go.bat
bin\iconCut-go.exe

# macOS / Linux
chmod +x build-go.sh
./build-go.sh
./bin/iconCut-go
```

## 体积对比（本机构建后填入）
| 方案 | 单文件 exe | 说明 |
|------|-----------|------|
| Python + PySide6 (PyInstaller) | ~107 MB | 打包 CPython + Qt6 |
| **Go + Fyne** | _待本机构建后填写_ | 待补充 |

## 已知限制（原型阶段）
- 未设置自定义窗口/文件图标（沿用 Fyne 默认），正式版需补 `.ico`/`.icns`
- 仅实现核心抠色链路，暂无撤销栈、套索、仅边缘扣色等进阶功能
- 坐标映射假设画布 1:1 显示，超高 DPI 下需进一步校准
