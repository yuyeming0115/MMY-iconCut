# iconCut launcher (Windows PowerShell)
# Auto-detect a usable Python (with standard library)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

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
    Write-Host "[ERROR] No usable Python found (standard library required)." -ForegroundColor Red
    Write-Host "The python in PATH may be an embeddable/stripped build."
    Write-Host "Please install official Python 3.11-3.13 and add it to PATH:"
    Write-Host "  https://www.python.org/downloads/"
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[iconCut] Python: $pyExe" -ForegroundColor Green

# Auto-install missing deps
& $pyExe -c "import PySide6, cv2, numpy, PIL" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[iconCut] Installing dependencies..." -ForegroundColor Yellow
    & $pyExe -m pip install -r (Join-Path $ScriptDir "requirements.txt")
}

& $pyExe (Join-Path $ScriptDir "main.py")
