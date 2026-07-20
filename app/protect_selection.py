"""保护选区管理:矢量化选区列表 + 撤销栈.

用多边形(套索)/掩膜(魔棒 flood fill)的选区列表替代旧的逐像素 BrushMask,
渲染时统一合成到一张保护 mask,支持加选/减选、合成缓存、撤销/重做.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from .tools import MAX_UNDO_STEPS


@dataclass
class SelectionItem:
    """单个保护选区项.

    Attributes:
        kind: "polygon" 或 "mask"
        data: 多边形点列表 list[tuple[int,int]] 或 (H,W) bool 掩膜
        subtract: True=减选,False=加选
    """

    kind: str
    data: list | np.ndarray
    subtract: bool = False


class ProtectSelection:
    """保护选区管理器.

    用矢量化的选区列表(多边形/掩膜)替代逐像素 mask,
    支持加选/减选、合成缓存、撤销/重做(粒度=每次 add 操作).
    """

    def __init__(self, h: int, w: int) -> None:
        self.h = h
        self.w = w
        # 当前选区列表
        self.selections: list[SelectionItem] = []
        # 撤销/重做栈,存选区列表的深拷贝
        self._undo: list[list[SelectionItem]] = []
        self._redo: list[list[SelectionItem]] = []
        # 合成缓存:_dirty 标记选区列表是否变更过
        self._dirty: bool = True
        self._cached_mask: np.ndarray = np.zeros((h, w), dtype=np.uint8)

    # ---- 撤销点 ----
    def _snapshot(self) -> None:
        """把当前选区列表的深拷贝压入撤销栈."""
        self._undo.append(copy.deepcopy(self.selections))
        if len(self._undo) > MAX_UNDO_STEPS:
            self._undo.pop(0)
        self._redo.clear()

    # ---- 添加选区 ----
    def add_polygon(
        self, points: list[tuple[int, int]], subtract: bool = False
    ) -> None:
        """追加多边形(套索)选区,记录撤销点."""
        self._snapshot()
        # 拷贝点列表并归一为 int 元组,避免外部修改影响内部
        pts = [tuple(int(v) for v in p) for p in points]
        self.selections.append(
            SelectionItem(kind="polygon", data=pts, subtract=subtract)
        )
        self._dirty = True

    def add_mask(self, mask: np.ndarray, subtract: bool = False) -> None:
        """追加掩膜(魔棒 flood fill)选区,记录撤销点."""
        self._snapshot()
        # 拷贝布尔掩膜,避免外部修改影响内部
        self.selections.append(
            SelectionItem(
                kind="mask",
                data=np.asarray(mask, dtype=bool).copy(),
                subtract=subtract,
            )
        )
        self._dirty = True

    # ---- 合成 ----
    def compose_mask(self) -> np.ndarray:
        """合成当前保护 mask (H,W) uint8,>0 表示保护.

        带缓存:选区列表未变时返回缓存的数组(同一对象).
        合成逻辑:从全 0 开始,加选用 |=,减选用 &= ~.
        """
        if not self._dirty:
            return self._cached_mask

        out = np.zeros((self.h, self.w), dtype=np.uint8)
        for item in self.selections:
            if item.kind == "polygon":
                filled = self._fill_polygon(item.data)
            else:
                filled = np.asarray(item.data, dtype=bool)

            filled_u8 = filled.astype(np.uint8) * 255
            if item.subtract:
                out &= ~filled_u8
            else:
                out |= filled_u8

        self._cached_mask = out
        self._dirty = False
        return out

    def _fill_polygon(self, points: list[tuple[int, int]]) -> np.ndarray:
        """用 cv2.fillPoly 填充多边形,返回 (H,W) bool 掩膜."""
        mask = np.zeros((self.h, self.w), dtype=np.uint8)
        if len(points) < 3:
            return mask.astype(bool)
        try:
            import cv2

            pts = np.array(points, dtype=np.int32).reshape(-1, 1, 2)
            cv2.fillPoly(mask, [pts], 1)
        except ImportError:
            # 无 cv2 时退化为多边形外接矩形(粗略填充)
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x0, x1 = max(0, min(xs)), min(self.w, max(xs) + 1)
            y0, y1 = max(0, min(ys)), min(self.h, max(ys) + 1)
            mask[y0:y1, x0:x1] = 1
        return mask.astype(bool)

    # ---- 重置 ----
    def reset(self) -> None:
        """清空选区和撤销栈."""
        self.selections.clear()
        self._undo.clear()
        self._redo.clear()
        self._dirty = True
        self._cached_mask = np.zeros((self.h, self.w), dtype=np.uint8)

    # ---- 撤销/重做 ----
    def undo(self) -> bool:
        """撤销最近一次 add 操作,成功返回 True."""
        if not self._undo:
            return False
        self._redo.append(copy.deepcopy(self.selections))
        self.selections = self._undo.pop()
        self._dirty = True
        return True

    def redo(self) -> bool:
        """重做最近一次撤销,成功返回 True."""
        if not self._redo:
            return False
        self._undo.append(copy.deepcopy(self.selections))
        self.selections = self._redo.pop()
        self._dirty = True
        return True

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)
