@echo off
REM MMY iconCut · Go+Fyne 原型 一键构建(Windows)
REM 前置: 已安装 Go(https://go.dev/dl/) 与 MinGW-w64(gcc, 因 Fyne 依赖 CGO)
REM 若 gcc 不在 PATH,请先安装 winlibs MinGW-w64 UCRT64 并加入 PATH
setlocal
cd /d "%~dp0"
where gcc >nul 2>nul || echo [警告] 未检测到 gcc,Fyne 需要 CGO,请先安装 MinGW-w64 并加入 PATH
go build -ldflags="-s -w" -o bin\iconCut-go.exe . || exit /b 1
echo 构建完成: bin\iconCut-go.exe
endlocal
