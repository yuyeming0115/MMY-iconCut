# iconCut

图标抠色 GUI 工具 —— 拖拽图片进去,吸取要扣掉的颜色,用笔刷涂出保护区,导出带透明通道的 PNG。

适用于处理 icon 图标的边缘杂色扣除、纯色背景扣除等场景。

## 功能特性

- **拖拽导入**:支持 PNG / JPG / JPEG / BMP / WEBP
- **吸管取色**:点击画布吸取要扣掉的颜色,可多次吸取(点击色块移除)
- **颜色扣除**:基于 RGB 距离 + 容差滑块,可调边缘羽化
- **保护笔刷**:涂抹不希望被扣的区域,保护区内即便命中颜色也不扣
  - 笔刷大小可调,带光标圆环预览
  - 橡皮擦模式,右键临时切换为橡皮
  - 笔刷拖动已做缓存优化,流畅不卡
- **自动检测保护区**:拖入透明背景的 icon / logo 时,自动把中心内容设为保护区(收缩边缘避开杂色);也可手动按 `A` 触发
- **仅边缘扣色**:只扣图片边缘 N 像素内的命中色,保护中心主体(适合 icon 边缘杂色处理)
- **三视图预览**:原图 / 结果(棋盘格背景)/ Alpha 蒙版
- **撤销 / 重做**:笔刷操作支持撤销栈
- **缩放平移**:鼠标滚轮缩放(以光标为中心),`F` 适应窗口
- **导出 PNG**:带 Alpha 通道

## 环境要求

- **Python 3.11 - 3.13**(需为官方完整版,含标准库)
- 跨平台:Windows / macOS / Linux

> ⚠️ 注意:Windows 商店版或 embeddable 精简版 Python 缺少标准库,运行会报 `No module named 'encodings'`。请到 [python.org](https://www.python.org/downloads/) 下载官方安装包,安装时勾选 **Add Python to PATH**。
>
> 不建议使用 Python 3.14(部分依赖可能尚无预编译包)。

### 依赖

- PySide6 >= 6.6
- opencv-python >= 4.8
- numpy >= 1.24
- Pillow >= 10.0

## 快速开始

### 方式一:一键脚本(推荐)

**Windows**:双击 `run.bat`,或在 PowerShell 中执行:

```powershell
.\run.ps1
```

脚本会自动探测可用 Python(跳过精简版/embeddable 版)、首次运行自动安装依赖。

**macOS / Linux**:

```bash
chmod +x run.sh
./run.sh
```

### 方式二:手动命令

```bash
pip install -r requirements.txt
python main.py
```

## 打包为单文件(便携版)

一键脚本会自动完成: 探测 Python(跳过精简版/embeddable 版) → 生成 Windows(`.ico`)/macOS(`.icns`) 图标 → PyInstaller 打包为**单文件**。

**Windows**(生成 `dist\iconCut.exe`,可拷贝到任意机器双击运行):

```powershell
.\build.ps1        # 或双击 build.bat
```

**macOS**(生成 `dist/iconCut.app`,可直接拷贝到其他 Mac 运行的便携包):

```bash
chmod +x build.sh
./build.sh
```

**Linux**(生成 `dist/iconCut`):同上 `./build.sh`。

- 图标来自 `图标/MMY-AI-Studio-icon.png`,由 `tools/make_icons.py` 自动转换为 `图标/MMY-AI-Studio-icon.ico`(Windows exe 文件图标)与 `MMY-AI-Studio-icon.icns`(macOS app 图标)。
- 手动重生成图标: `python tools/make_icons.py`
- ⚠️ Windows 重新打包后,若资源管理器仍显示旧图标:在 `dist\` 目录刷新,或重启资源管理器(Windows 按文件路径缓存 exe 图标)。

## 快捷键

| 快捷键 | 功能 | 快捷键 | 功能 |
| --- | --- | --- | --- |
| `E` | 吸管工具 | `B` | 保护笔刷 |
| `X` | 橡皮擦 | `A` | 自动检测保护区 |
| `F` | 适应窗口 | | |
| `1` / `2` / `3` | 切换 原图 / 结果 / Alpha 视图 | `[` / `]` | 缩小 / 放大笔刷 |
| `Ctrl+Z` | 撤销 | `Ctrl+Y` | 重做 |
| `Ctrl+O` | 导入图片 | `Ctrl+S` | 导出 PNG |
| 鼠标滚轮 | 缩放画布 | 右键(笔刷/橡皮下) | 临时橡皮 |

## 使用流程

1. **导入**:拖拽图片到窗口,或点「导入图片」/ `Ctrl+O`
2. **吸色**:选吸管工具(`E`),点击要扣掉的颜色(可多次吸,点击色块移除)
3. **调参**:拖动「容差」扩大相似色范围;「羽化」给边缘做柔化
4. **保护**:切到保护笔刷(`B`),涂抹不希望被扣的区域
5. **边缘模式**(可选):勾选「仅边缘扣色」,只扣图片边缘 N 像素内的命中色
6. **预览**:右栏切换 原图(`1`)/ 结果(`2`)/ Alpha 蒙版(`3`)
7. **导出**:点「导出 PNG」或 `Ctrl+S`

## 目录结构

```
MMY-iconCut/
├── main.py                 # 入口
├── requirements.txt        # 依赖
├── run.ps1 / run.bat       # Windows 启动脚本(ps1 主逻辑)
├── run.sh                  # macOS / Linux 启动脚本
├── build.ps1 / build.bat   # Windows 打包脚本
├── build.sh                # macOS / Linux 打包脚本
├── tools/
│   └── make_icons.py       # 从 PNG 生成 ICO/ICNS 图标
├── 图标/                    # 应用图标资源
│   ├── MMY-AI-Studio-icon.png
│   ├── MMY-AI-Studio-icon.ico   # 自动生成(Windows exe 文件图标)
│   └── MMY-AI-Studio-icon.icns   # 自动生成(macOS app 图标)
└── app/
    ├── __init__.py
    ├── tools.py            # 工具/视图枚举、常量
    ├── image_processor.py  # 抠色、Alpha 合成、边缘掩膜、棋盘格、导出
    ├── brush_mask.py       # 保护笔刷 mask + 撤销栈
    ├── canvas.py           # 画布:拖拽/吸管/笔刷/缩放/三视图/光标圆环
    └── main_window.py      # 三栏布局 + 菜单 + 快捷键
```

## 技术栈

- **GUI**:PySide6 (Qt6)
- **图像处理**:OpenCV + NumPy
- **图像 IO**:Pillow
- **打包**:PyInstaller

## 仓库

- GitHub: https://github.com/yuyeming0115/MMY-iconCut
