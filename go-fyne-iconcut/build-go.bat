@echo off
REM MMY iconCut Go+Fyne prototype - Windows one-shot build
REM Requires: Go (https://go.dev/dl/) and MinGW-w64 gcc (Fyne needs CGO)
REM If gcc/go are not on PATH, this script auto-adds the known install dir

setlocal
cd /d "%~dp0"

set "GOBIN=C:\Users\EDY\.workbuddy\binaries\go\bin"
set "MINGWBIN=C:\Users\EDY\.workbuddy\binaries\mingw64\bin"

REM ensure go on PATH
where go >nul 2>nul
if errorlevel 1 (
  if exist "%GOBIN%\go.exe" set "PATH=%GOBIN%;%PATH%"
)

REM ensure gcc on PATH
where gcc >nul 2>nul
if errorlevel 1 (
  if exist "%MINGWBIN%\gcc.exe" set "PATH=%MINGWBIN%;%PATH%"
)

where gcc >nul 2>nul
if errorlevel 1 (
  echo [ERROR] gcc not found. Install winlibs MinGW-w64 UCRT64 and add its bin to PATH.
  exit /b 1
)

where go >nul 2>nul
if errorlevel 1 (
  echo [ERROR] go not found. Install Go 1.23+ and add its bin to PATH.
  exit /b 1
)

set "CGO_ENABLED=1"
set "CC=gcc"
set "CGO_LDFLAGS=-static -static-libgcc -static-libstdc++"

if not exist "bin" mkdir bin

echo ===================================================
echo  Building iconCut-go.exe ...
echo  First build compiles Fyne CGO (C) dependencies and
echo  may take several minutes with little visible output.
echo  This is normal - do NOT close this window.
echo ===================================================

go build -v -ldflags="-H=windowsgui -s -w -extldflags=-static" -o bin\iconCut-go.exe .
if errorlevel 1 (
  echo [ERROR] build failed.
  exit /b 1
)

echo Build done: bin\iconCut-go.exe
endlocal
