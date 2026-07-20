# iconCut build script (Windows PowerShell) - single-file exe with icon
# 一键打包: 探测 Python -> 生成图标(ICO/ICNS) -> PyInstaller 单文件 exe
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# ---------------------------------------------------------------------------
# 1) 探测可用 Python（跳过精简版 / embeddable 版，它们缺标准库会报 encodings 错误）
# ---------------------------------------------------------------------------
$candidates = @()
foreach ($n in @("python", "python3")) {
    $found = Get-Command $n -ErrorAction SilentlyContinue
    if ($found) { $candidates += $found.Source }
}
$extra = @(
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "C:\Python313\python.exe",
    "C:\Python312\python.exe",
    "$env:USERPROFILE\.workbuddy\binaries\python\versions\3.13.12\python.exe"
)
foreach ($p in $extra) {
    if ($p -and (Test-Path $p) -and ($candidates -notcontains $p)) { $candidates += $p }
}

$pyExe = $null
foreach ($p in $candidates) {
    try {
        & $p -c "import encodings" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $pyExe = $p; break }
    } catch { }
}
if (-not $pyExe) {
    Write-Host "[ERROR] 未找到可用的 Python(需官方完整版,含标准库)。" -ForegroundColor Red
    Write-Host "请将官方 Python 3.11-3.13 加入 PATH: https://www.python.org/downloads/"
    Read-Host "按 Enter 退出"
    exit 1
}

Write-Host "[iconCut] Python: $pyExe" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 2) 安装 PyInstaller
# ---------------------------------------------------------------------------
Write-Host "[iconCut] 安装 PyInstaller..." -ForegroundColor Yellow
& $pyExe -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller 安装失败。" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# ---------------------------------------------------------------------------
# 3) 生成图标 (ICO 给 Windows, ICNS 给 macOS)
# ---------------------------------------------------------------------------
$png = Get-ChildItem -Path $ScriptDir -Recurse -Filter "MMY-AI-Studio-icon.png" -Depth 2 | Select-Object -First 1
if (-not $png) {
    Write-Host "[ERROR] 未找到 图标/MMY-AI-Studio-icon.png" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}
# 确保 Pillow 可用(图标生成需要)
& $pyExe -c "import PIL" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[iconCut] 安装 Pillow(图标生成)..." -ForegroundColor Yellow
    & $pyExe -m pip install Pillow
}
$iconTool = [System.IO.Path]::Combine($ScriptDir, "tools", "make_icons.py")
Write-Host "[iconCut] 生成图标..." -ForegroundColor Yellow
& $pyExe $iconTool $png.FullName $png.DirectoryName
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] 图标生成失败。" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}
$ico = Join-Path $png.DirectoryName "MMY-AI-Studio-icon.ico"
if (-not (Test-Path $ico)) {
    Write-Host "[ERROR] 未生成 ICO: $ico" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# ---------------------------------------------------------------------------
# 4) 清理旧产物(避免 Windows 图标缓存导致新图标不刷新)
# ---------------------------------------------------------------------------
$outExe = [System.IO.Path]::Combine($ScriptDir, "dist", "iconCut.exe")
if (Test-Path $outExe) { Remove-Item $outExe -Force }

# ---------------------------------------------------------------------------
# 5) 打包: 单文件 + 无控制台窗口 + 自定义图标 + 打包图标资源目录
# ---------------------------------------------------------------------------
$iconDir = $png.DirectoryName
$iconName = (Get-Item $iconDir).Name   # 可能是中文 "图标"
Write-Host "[iconCut] 打包中... (--onefile --windowed --icon)" -ForegroundColor Yellow
& $pyExe -m PyInstaller --onefile --windowed --name iconCut --icon $ico --add-data "${iconName};${iconName}" (Join-Path $ScriptDir "main.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] PyInstaller 打包失败。" -ForegroundColor Red
    Read-Host "按 Enter 退出"
    exit 1
}

# ---------------------------------------------------------------------------
# 6) 完成
# ---------------------------------------------------------------------------
$size = [math]::Round((Get-Item $outExe).Length / 1MB, 1)
Write-Host ""
Write-Host "[iconCut] 完成! 单文件 exe: dist\iconCut.exe ($size MB)" -ForegroundColor Green
Write-Host "[iconCut] 可直接拷贝到任意 Windows 机器运行,无需安装。" -ForegroundColor Cyan
Write-Host ""
Write-Host "[提示] 若资源管理器仍显示旧图标: 在 dist\ 目录右键刷新,或重启资源管理器。" -ForegroundColor DarkGray
Read-Host "按 Enter 退出"
