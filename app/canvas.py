"""画布 QWidget:拖拽导入、显示、吸管、魔棒保护、套索、视图切换."""
from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal, QSize, QPoint, QPointF, QMimeData
from PySide6.QtGui import (
    QImage,
    QPainter,
    QPixmap,
    QColor,
    QPen,
    QPolygon,
    QMouseEvent,
    QWheelEvent,
    QPaintEvent,
    QDragEnterEvent,
    QDropEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import QWidget

from .tools import (
    Tool,
    ViewMode,
    PROTECT_OVERLAY_RGBA,
    LASSO_OVERLAY_COLOR,
    LASSO_SUBTRACT_COLOR,
    CHECKER_SIZE,
)
from .protect_selection import ProtectSelection
from . import image_processor as ip


class ImageCanvas(QWidget):
    """图像画布.

    Signals:
        color_picked(rgb): 吸管取色完成
        image_loaded(path): 图片加载完成
        mask_changed(): 保护 mask 改变
        cursor_pixel(rgb): 鼠标悬停像素颜色
    """

    color_picked = Signal(tuple)
    image_loaded = Signal(str)
    mask_changed = Signal()
    cursor_pixel = Signal(tuple)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(480, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # 状态
        self._rgba: Optional[np.ndarray] = None       # 原图 RGBA (H,W,4)
        self._image_path: Optional[str] = None
        self._protect: Optional[ProtectSelection] = None
        # 吸管抠色选区:每项 (颜色rgb, 种子点(x,y), 连通mask)
        # 点击时用 flood fill 生成连通区域,只扣该连通块.
        self._wand_entries: list[tuple[tuple[int, int, int], tuple[int, int], np.ndarray]] = []
        self._tolerance: int = 32
        self._feather: int = 0
        self._edge_mode: bool = False
        self._edge_width: int = 8
        self._tool: Tool = Tool.EYEDROPPER
        self._view: ViewMode = ViewMode.RESULT
        self._show_protect: bool = True

        # 缩放与平移
        self._zoom: float = 1.0
        self._offset = QPointF(0, 0)   # 画布左上角在 widget 中的位置

        # 套索临时路径(widget 坐标点列表)
        self._lasso_points: list[QPoint] = []
        self._lasso_active: bool = False

        # 显示用缓存
        self._display_cache: Optional[QPixmap] = None
        self._cache_dirty: bool = True
        # 性能缓存:hit_mask 和 checker 只在颜色/容差/图片尺寸变化时重算.
        self._hit_mask: Optional[np.ndarray] = None
        self._hit_dirty: bool = True
        self._checker: Optional[np.ndarray] = None

    # ---------- 公开接口 ----------

    def load_image_path(self, path: str) -> None:
        arr = ip.load_image(path)
        self._rgba = arr
        self._image_path = path
        self._protect = ProtectSelection(arr.shape[0], arr.shape[1])
        self._wand_entries.clear()
        # 图片更换:hit 与 checker 全部失效
        self._hit_dirty = True
        self._checker = None
        self._cache_dirty = True
        self._fit_to_view()
        self.update()
        self.image_loaded.emit(path)

    def auto_detect_protect(self) -> bool:
        """自动检测透明背景 icon 的中心内容,设为保护区域.

        判定:四角 alpha 接近透明则视为透明背景 icon/logo.
        将非透明内容收缩若干像素作为保护 mask(避开边缘杂色).
        """
        if self._rgba is None or self._protect is None:
            return False
        alpha = self._rgba[..., 3]
        # 取四角小块均值判断背景是否透明
        sample = 3
        corners = [
            alpha[:sample, :sample].mean(),
            alpha[:sample, -sample:].mean(),
            alpha[-sample:, :sample].mean(),
            alpha[-sample:, -sample:].mean(),
        ]
        if not all(c < 96 for c in corners):
            return False  # 非透明背景,不自动设
        # 非透明内容
        content = alpha >= 128
        # 收缩边缘像素,避免把杂色边缘纳入保护
        try:
            import cv2
            k = 5
            eroded = cv2.erode(
                content.astype(np.uint8) * 255,
                np.ones((k, k), np.uint8),
                iterations=1,
            )
            mask = eroded > 0
        except ImportError:
            mask = content
        # 先清空再设(替换式)
        self._protect.reset()
        self._protect.add_mask(mask, subtract=False)
        self._cache_dirty = True
        self.mask_changed.emit()
        self.update()
        return True

    def set_tool(self, tool: Tool) -> None:
        self._tool = tool
        self.setCursor(self._cursor_for_tool(tool))

    def set_view_mode(self, mode: ViewMode) -> None:
        self._view = mode
        self._cache_dirty = True
        self.update()

    def set_tolerance(self, v: int) -> None:
        self._tolerance = int(v)
        # 容差改变后重新生成所有吸管抠色选区(用种子点重新 flood fill)
        self._regenerate_wand_masks()
        self._hit_dirty = True
        self._cache_dirty = True
        self.update()

    def _regenerate_wand_masks(self) -> None:
        """容差改变后,用每个吸管选区的种子点重新 flood fill."""
        if not self._wand_entries or self._rgba is None:
            return
        new_entries = []
        for rgb, seed, _ in self._wand_entries:
            mask = ip.flood_fill_select(self._rgba, seed[0], seed[1], self._tolerance)
            new_entries.append((rgb, seed, mask))
        self._wand_entries = new_entries

    def set_feather(self, v: int) -> None:
        self._feather = int(v)
        self._cache_dirty = True
        self.update()

    def set_edge_mode(self, on: bool) -> None:
        self._edge_mode = bool(on)
        self._hit_dirty = True
        self._cache_dirty = True
        self.update()

    def set_edge_width(self, v: int) -> None:
        self._edge_width = int(v)
        self._hit_dirty = True
        self._cache_dirty = True
        self.update()

    def set_show_protect(self, on: bool) -> None:
        self._show_protect = on
        self._cache_dirty = True
        self.update()

    def get_picked_colors(self) -> list[tuple[int, int, int]]:
        return [e[0] for e in self._wand_entries]

    def add_picked_color(self, rgb: tuple[int, int, int]) -> None:
        """吸管取色后由 main_window 调用(无种子点时用全图颜色匹配)."""
        self.add_wand_selection(rgb, None)

    def add_wand_selection(self, rgb: tuple[int, int, int], seed: Optional[tuple[int, int]]) -> None:
        """添加吸管抠色选区. seed=None 时退化为全图颜色匹配."""
        if self._rgba is None:
            return
        if seed is not None:
            mask = ip.flood_fill_select(self._rgba, seed[0], seed[1], self._tolerance)
        else:
            mask = ip.compute_color_mask(self._rgba[..., :3], [rgb], self._tolerance)
        # 同色替换
        self._wand_entries = [e for e in self._wand_entries if e[0] != rgb]
        self._wand_entries.append((rgb, seed if seed else (0, 0), mask))
        self._hit_dirty = True
        self._cache_dirty = True
        self.update()

    def remove_picked_color(self, rgb: tuple[int, int, int]) -> None:
        self._wand_entries = [e for e in self._wand_entries if e[0] != rgb]
        self._hit_dirty = True
        self._cache_dirty = True
        self.update()

    def clear_picked_colors(self) -> None:
        self._wand_entries.clear()
        self._hit_dirty = True
        self._cache_dirty = True
        self.update()

    def clear_protect(self) -> None:
        if self._protect is not None:
            self._protect.reset()
            self._cache_dirty = True
            self.mask_changed.emit()
            self.update()

    def undo(self) -> None:
        if self._protect and self._protect.undo():
            self._cache_dirty = True
            self.mask_changed.emit()
            self.update()

    def redo(self) -> None:
        if self._protect and self._protect.redo():
            self._cache_dirty = True
            self.mask_changed.emit()
            self.update()

    def can_undo(self) -> bool:
        return bool(self._protect and self._protect.can_undo())

    def can_redo(self) -> bool:
        return bool(self._protect and self._protect.can_redo())

    def _ensure_hit_mask(self) -> None:
        """(重新)计算命中扣色掩膜 = 所有吸管选区的并集,带缓存."""
        if self._rgba is None:
            return
        if not self._hit_dirty and self._hit_mask is not None:
            return
        h, w = self._rgba.shape[:2]
        hit = np.zeros((h, w), dtype=bool)
        for _rgb, _seed, mask in self._wand_entries:
            hit |= mask
        if self._edge_mode:
            hit = hit & ip.compute_edge_mask(h, w, self._edge_width)
        self._hit_mask = hit
        self._hit_dirty = False

    def _ensure_checker(self) -> None:
        if self._rgba is None:
            return
        if self._checker is not None and self._checker.shape[:2] == self._rgba.shape[:2]:
            return
        h, w = self._rgba.shape[:2]
        self._checker = ip.make_checkerboard(h, w, CHECKER_SIZE)

    def get_result_rgba(self) -> Optional[np.ndarray]:
        """返回当前结果 RGBA(应用了抠色、边缘模式与保护)."""
        if self._rgba is None:
            return None
        h, w = self._rgba.shape[:2]
        protect = self._protect.compose_mask() if self._protect is not None else np.zeros((h, w), np.uint8)
        self._ensure_hit_mask()
        hit = self._hit_mask if self._hit_mask is not None else np.zeros((h, w), dtype=bool)
        alpha = ip.compose_alpha(hit, protect, self._feather)
        return ip.apply_alpha(self._rgba, alpha)

    def has_image(self) -> bool:
        return self._rgba is not None

    # ---------- 拖拽 ----------

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasUrls():
            urls = e.mimeData().urls()
            if any(self._is_image_url(u) for u in urls):
                e.acceptProposedAction()
                return
        e.ignore()

    def dropEvent(self, e: QDropEvent) -> None:
        for u in e.mimeData().urls():
            path = u.toLocalFile()
            if path and self._is_image_path(path):
                self.load_image_path(path)
                e.acceptProposedAction()
                return
        e.ignore()

    @staticmethod
    def _is_image_url(u) -> bool:
        path = u.toLocalFile()
        return bool(path) and ImageCanvas._is_image_path(path)

    @staticmethod
    def _is_image_path(path: str) -> bool:
        return path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp"))

    # ---------- 缩放/适应 ----------

    def _fit_to_view(self) -> None:
        if self._rgba is None:
            return
        iw, ih = self._rgba.shape[1], self._rgba.shape[0]
        cw, ch = self.width(), self.height()
        if cw <= 0 or ch <= 0:
            return
        z = min(cw / iw, ch / ih, 1.0) if min(cw, ch) > 0 else 1.0
        z = max(z, min(1.0, z))
        self._zoom = z
        self._offset = QPointF(
            (cw - iw * z) / 2.0,
            (ch - ih * z) / 2.0,
        )

    def set_zoom(self, z: float) -> None:
        self._zoom = max(0.05, min(16.0, z))
        self.update()

    def get_zoom(self) -> float:
        return self._zoom

    # ---------- 鼠标 ----------

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if self._rgba is None:
            return
        pos = e.position().toPoint()
        img_pt = self._widget_to_image(pos)
        subtract = bool(e.modifiers() & Qt.AltModifier)

        if e.button() == Qt.LeftButton:
            if self._tool == Tool.EYEDROPPER:
                if img_pt is None:
                    return
                x, y = img_pt
                rgb = tuple(int(v) for v in self._rgba[y, x, :3])
                # 吸管:全图颜色匹配(扣掉所有相同颜色)
                self.add_picked_color(rgb)
                self.color_picked.emit(rgb)
            elif self._tool == Tool.WAND:
                if img_pt is None:
                    return
                x, y = img_pt
                rgb = tuple(int(v) for v in self._rgba[y, x, :3])
                # 魔棒:从点击点 flood fill 选中连通区域作为抠色选区,
                # 只扣该连通块,不会扣到 logo 内部同色区域.
                self.add_wand_selection(rgb, (x, y))
                self.color_picked.emit(rgb)
            elif self._tool == Tool.LASSO:
                # 开始套索
                self._lasso_active = True
                self._lasso_points = [pos]

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = e.position().toPoint()
        img_pt = self._widget_to_image(pos)
        if img_pt is not None and self._rgba is not None:
            x, y = img_pt
            rgb = tuple(int(v) for v in self._rgba[y, x, :3])
            self.cursor_pixel.emit(rgb)
        if self._lasso_active:
            self._lasso_points.append(pos)
            # 只刷新画临时线条,不触发 mask 重算(_cache_dirty 未设)
            self.update()

    def leaveEvent(self, e) -> None:
        super().leaveEvent(e)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.LeftButton and self._lasso_active:
            self._lasso_active = False
            if len(self._lasso_points) >= 3 and self._protect is not None:
                # 闭合多边形:把 widget 坐标转为 image 坐标
                img_pts: list[tuple[int, int]] = []
                for wp in self._lasso_points:
                    ip_pt = self._widget_to_image(wp)
                    if ip_pt is not None:
                        img_pts.append(ip_pt)
                if len(img_pts) >= 3:
                    subtract = bool(e.modifiers() & Qt.AltModifier)
                    self._protect.add_polygon(img_pts, subtract=subtract)
                    self._cache_dirty = True
                    self.mask_changed.emit()
            self._lasso_points.clear()
            self.update()

    def wheelEvent(self, e: QWheelEvent) -> None:
        if self._rgba is None:
            return
        delta = e.angleDelta().y()
        if delta == 0:
            return
        # 以鼠标为中心缩放
        pos = e.position()
        old_z = self._zoom
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_z = max(0.05, min(16.0, old_z * factor))
        # 保持鼠标点对应的图像像素不变
        img_x = (pos.x() - self._offset.x()) / old_z
        img_y = (pos.y() - self._offset.y()) / old_z
        self._zoom = new_z
        self._offset = QPointF(pos.x() - img_x * new_z, pos.y() - img_y * new_z)
        self.update()

    def resizeEvent(self, e: QResizeEvent) -> None:
        super().resizeEvent(e)
        if self._rgba is not None and self._offset == QPointF(0, 0):
            self._fit_to_view()

    # ---------- 坐标转换 ----------

    def _widget_to_image(self, pos: QPoint) -> Optional[tuple[int, int]]:
        if self._rgba is None:
            return None
        ix = (pos.x() - self._offset.x()) / self._zoom
        iy = (pos.y() - self._offset.y()) / self._zoom
        x = int(round(ix))
        y = int(round(iy))
        h, w = self._rgba.shape[:2]
        if 0 <= x < w and 0 <= y < h:
            return x, y
        return None

    # ---------- 绘制 ----------

    def paintEvent(self, e: QPaintEvent) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(45, 45, 48))

        if self._rgba is None:
            p.setPen(QColor(180, 180, 180))
            p.drawText(self.rect(), Qt.AlignCenter, "拖拽图片到此处  /  点击「导入图片」")
            return

        if self._cache_dirty:
            self._rebuild_cache()
            self._cache_dirty = False

        if self._display_cache is not None:
            pix = self._display_cache
            sz = pix.size()
            target = QSize(int(sz.width() * self._zoom), int(sz.height() * self._zoom))
            p.setRenderHint(QPainter.SmoothPixmapTransform, self._zoom < 1.0)
            p.drawPixmap(self._offset.toPoint(), pix.scaled(
                target, Qt.KeepAspectRatio, Qt.FastTransformation
            ))

        # 套索临时线条(拖动期间只画线,不重算 mask)
        if self._lasso_active and len(self._lasso_points) >= 2:
            from PySide6.QtWidgets import QApplication
            subtract = bool(QApplication.keyboardModifiers() & Qt.AltModifier)
            color = LASSO_SUBTRACT_COLOR if subtract else LASSO_OVERLAY_COLOR
            pen = QPen(QColor(*color), 2)
            pen.setCosmetic(True)
            p.setPen(pen)
            poly = QPolygon(self._lasso_points)
            p.drawPolyline(poly)

        p.end()

    def _rebuild_cache(self) -> None:
        """根据当前 view 重建显示缓存(原图尺寸)."""
        if self._rgba is None:
            return
        if self._view == ViewMode.ORIGINAL:
            arr = self._rgba[..., :3].copy()
        elif self._view == ViewMode.ALPHA:
            result = self.get_result_rgba()
            alpha = result[..., 3] if result is not None else np.full(self._rgba.shape[:2], 255, np.uint8)
            arr = ip.alpha_to_rgb_preview(alpha)
        else:  # RESULT
            result = self.get_result_rgba()
            if result is None:
                arr = self._rgba[..., :3].copy()
            else:
                self._ensure_checker()
                checker = self._checker if self._checker is not None else ip.make_checkerboard(
                    result.shape[0], result.shape[1], CHECKER_SIZE
                )
                arr = ip.compose_on_checker(result, checker)

        # 叠加保护区域显示
        if self._show_protect and self._protect is not None and self._view in (ViewMode.RESULT, ViewMode.ORIGINAL):
            protect_mask = self._protect.compose_mask() > 0
            if protect_mask.any():
                overlay = np.zeros(arr.shape, dtype=np.uint8)
                r, g, b, a = PROTECT_OVERLAY_RGBA
                overlay[protect_mask] = (r, g, b)
                alpha_o = np.zeros(arr.shape[:2], dtype=np.uint8)
                alpha_o[protect_mask] = a
                arr = self._blend(arr, overlay, alpha_o)

        self._display_cache = self._numpy_to_pixmap(arr)

    @staticmethod
    def _blend(base: np.ndarray, overlay: np.ndarray, alpha: np.ndarray) -> np.ndarray:
        a = alpha.astype(np.float32) / 255.0
        a3 = a[..., None]
        return (base.astype(np.float32) * (1 - a3) + overlay.astype(np.float32) * a3).astype(np.uint8)

    @staticmethod
    def _numpy_to_pixmap(arr: np.ndarray) -> QPixmap:
        h, w = arr.shape[:2]
        if arr.shape[2] == 3:
            rgba = np.concatenate([arr, np.full((h, w, 1), 255, np.uint8)], axis=2)
        else:
            rgba = arr
        rgba = np.ascontiguousarray(rgba)
        img = QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888)
        return QPixmap.fromImage(img.copy())

    def _cursor_for_tool(self, tool: Tool):
        return Qt.CrossCursor
