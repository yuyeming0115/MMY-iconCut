@echo off
REM iconCut packaging launcher - runs build.ps1 (single-file exe with icon)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
