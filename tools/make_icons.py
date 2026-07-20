#!/usr/bin/env python3
"""从源 PNG 生成 Windows(.ico) 与 macOS(.icns) 图标。

- ICO 手工拼装为 PNG-in-ICO 容器（Windows Vista+ 支持），保证每个尺寸都真实嵌入，
  绕开 Pillow save(ICO, sizes=...) 只写入首张尺寸的已知缺陷。
- ICNS 使用 Pillow 原生编码（自动生成 16/32/128/256/512/1024 多档）。

用法:
    python tools/make_icons.py
    python tools/make_icons.py <源png> [输出目录]
"""
from __future__ import annotations

import io
import os
import struct
import sys
from pathlib import Path

from PIL import Image, ImageFilter

# 需要嵌入 ICO 的尺寸（256 在 ICONDIRENTRY 中以 0 表示）
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _resolve_source(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise SystemExit(f"[错误] 源图标不存在: {p}")
        return p
    # 在脚本目录的父目录(项目根)下查找 图标/*.png
    here = Path(__file__).resolve().parent
    candidates = list(here.parent.glob("图标/*.png"))
    if not candidates:
        raise SystemExit("[错误] 未找到 图标/*.png，请显式传入源 PNG 路径。")
    return candidates[0]


def make_ico(src: Path, out: Path) -> None:
    im = Image.open(src).convert("RGBA")
    pngs: list[bytes] = []
    for s in ICO_SIZES:
        r = im.resize((s, s), Image.LANCZOS)
        # 小尺寸锐化，避免缩小后发糊
        if s <= 48:
            r = r.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=2))
        buf = io.BytesIO()
        r.save(buf, format="PNG")
        pngs.append(buf.getvalue())

    header = struct.pack("<HHH", 0, 1, len(pngs))
    entries = b""
    data = b""
    offset = 6 + 16 * len(pngs)
    for png, s in zip(pngs, ICO_SIZES):
        w = s if s < 256 else 0
        h = s if s < 256 else 0
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png), offset + len(data))
        data += png

    out.write_bytes(header + entries + data)


def make_icns(src: Path, out: Path) -> None:
    im = Image.open(src).convert("RGBA")
    # ICNS 编码器会对大图自动下采样出多档；给一张足够大的正方形源即可
    im.save(out, format="ICNS")


def main() -> None:
    src = _resolve_source(sys.argv[1] if len(sys.argv) > 1 else None)
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    ico = out_dir / "MMY-AI-Studio-icon.ico"
    icns = out_dir / "MMY-AI-Studio-icon.icns"

    make_ico(src, ico)
    print(f"[OK] ICO  -> {ico}")

    try:
        make_icns(src, icns)
        print(f"[OK] ICNS -> {icns}")
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] ICNS 生成失败 ({e})，macOS 打包将跳过 --icon。")

    # 校验 ICO 多尺寸
    try:
        with Image.open(ico) as v:
            print(f"[校验] ICO 包含尺寸: {sorted(getattr(v, 'sizes', []))}")
    except Exception as e:  # noqa: BLE001
        print(f"[WARN] ICO 校验失败: {e}")


if __name__ == "__main__":
    main()
