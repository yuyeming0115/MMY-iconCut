@echo off
chcp 65001 >nul
REM iconCut 启动入口 (双击运行) - 调用 PowerShell 脚本
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
