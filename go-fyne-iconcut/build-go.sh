#!/usr/bin/env bash
# MMY iconCut · Go+Fyne 原型 一键构建(macOS / Linux)
# 前置: go + gcc(Fyne 依赖 CGO)
set -e
cd "$(dirname "$0")"
which gcc >/dev/null 2>&1 || { echo "[警告] 未检测到 gcc,Fyne 需要 CGO"; }
mkdir -p bin
go build -ldflags="-s -w" -o bin/iconCut-go .
echo "构建完成: bin/iconCut-go"
