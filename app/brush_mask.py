"""笔刷保护 mask 管理与撤销栈."""
from __future__ import annotations

import numpy as np

from .tools import MAX_UNDO_STEPS


class BrushMask:
    """保护区域 mask.

    mask: (H, W) uint8,>0 表示被保护.
    """

    def __init__(self, h: int, w: int) -> None:
        self.h = h
        self.w = w
        self.mask = np.zeros((h, w), dtype=np.uint8)
        # 撤销/重做栈,保存 mask 快照
        self._undo: list[np.ndarray] = []
        self._redo: list[np.ndarray] = []

    def reset(self) -> None:
        self.mask = np.zeros((self.h, self.w), dtype=np.uint8)
        self._undo.clear()
        self._redo.clear()

    def _snapshot(self) -> None:
        self._undo.append(self.mask.copy())
        if len(self._undo) > MAX_UNDO_STEPS:
            self._undo.pop(0)
        self._redo.clear()

    def begin_stroke(self) -> None:
        """开始一笔,记录撤销点."""
        self._snapshot()

    def paint(self, x: int, y: int, radius: int, erase: bool = False) -> None:
        """在 (x, y) 画一个圆,半径 radius.

        erase=True 时擦除保护区域.
        """
        y0 = max(0, y - radius)
        y1 = min(self.h, y + radius + 1)
        x0 = max(0, x - radius)
        x1 = min(self.w, x + radius + 1)
        if y0 >= y1 or x0 >= x1:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        circle = (yy - y) ** 2 + (xx - x) ** 2 <= radius * radius
        if erase:
            self.mask[y0:y1, x0:x1][circle] = 0
        else:
            self.mask[y0:y1, x0:x1][circle] = 255

    def paint_line(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        radius: int,
        erase: bool = False,
    ) -> None:
        """沿 (x0,y0) -> (x1,y1) 插值绘制连续笔画."""
        dist = max(abs(x1 - x0), abs(y1 - y0))
        steps = max(1, dist // max(1, radius // 3))
        for i in range(steps + 1):
            t = i / steps if steps else 0
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            self.paint(x, y, radius, erase)

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.mask.copy())
        self.mask = self._undo.pop()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.mask.copy())
        self.mask = self._redo.pop()
        return True

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)
