"""主窗口:三栏布局与信号连接."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence, QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QSlider,
    QLabel,
    QFileDialog,
    QMessageBox,
    QButtonGroup,
    QRadioButton,
    QCheckBox,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QGroupBox,
)

from .canvas import ImageCanvas
from .tools import (
    Tool,
    ViewMode,
    DEFAULT_TOLERANCE,
    DEFAULT_FEATHER,
)
from . import image_processor as ip


STYLE = """
QMainWindow, QWidget { background: #2d2d30; color: #e0e0e0; }
QGroupBox {
    border: 1px solid #3f3f46;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QPushButton {
    background: #3f3f46;
    border: 1px solid #4a4a52;
    border-radius: 3px;
    padding: 6px 10px;
}
QPushButton:hover { background: #4a4a52; }
QPushButton:pressed { background: #2a2a2e; }
QPushButton:checked { background: #007acc; border-color: #007acc; }
QPushButton:disabled { color: #707078; background: #2a2a2e; }
QSlider::groove:horizontal { height: 4px; background: #3f3f46; }
QSlider::handle:horizontal {
    background: #007acc; width: 14px; margin: -6px 0; border-radius: 7px;
}
QRadioButton { padding: 3px 0; }
QLabel { color: #c8c8c8; }
"""


class ColorSwatch(QLabel):
    """颜色色块,点击移除."""

    def __init__(self, rgb: tuple[int, int, int], on_remove):
        super().__init__()
        self.rgb = rgb
        self.on_remove = on_remove
        self.setFixedSize(QSize(28, 28))
        self.setToolTip(f"RGB{rgb}  点击移除")
        self._paint(rgb)
        self.setCursor(Qt.PointingHandCursor)

    def _paint(self, rgb):
        pix = QPixmap(28, 28)
        pix.fill(QColor(*rgb))
        # 加边框
        from PySide6.QtGui import QPainter, QPen
        p = QPainter(pix)
        p.setPen(QPen(QColor(0, 0, 0), 1))
        p.drawRect(0, 0, 27, 27)
        p.end()
        self.setPixmap(pix)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.on_remove(self.rgb)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("iconCut — 图标抠色工具")
        self.resize(1280, 820)
        self.setStyleSheet(STYLE)

        self.canvas = ImageCanvas()
        self._build_ui()
        self._connect_signals()

        # 初始工具
        self._set_tool(Tool.EYEDROPPER)
        self._set_view(ViewMode.RESULT)

    # ---------- UI 构建 ----------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        layout.addWidget(self._build_left_panel(), 0)
        layout.addWidget(self._build_canvas_area(), 1)
        layout.addWidget(self._build_right_panel(), 0)

        self._build_menu()

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(220)
        v = QVBoxLayout(panel)
        v.setSpacing(8)

        # 导入
        gb_io = QGroupBox("图片")
        g = QVBoxLayout(gb_io)
        self.btn_open = QPushButton("导入图片")
        self.btn_open.clicked.connect(self._on_open)
        g.addWidget(self.btn_open)
        v.addWidget(gb_io)

        # 工具
        gb_tool = QGroupBox("工具")
        g = QVBoxLayout(gb_tool)
        self.btn_tool_eyedropper = QPushButton("吸管 (E)")
        self.btn_tool_eyedropper.setCheckable(True)
        self.btn_tool_eyedropper.setToolTip("吸取颜色,扣掉全图所有相同颜色(容差内)")
        self.btn_tool_wand = QPushButton("魔棒 (W)")
        self.btn_tool_wand.setCheckable(True)
        self.btn_tool_wand.setToolTip("点击选中连通区域作为抠色选区,只扣该连通块(不扣 logo 内部同色)")
        self.btn_tool_lasso = QPushButton("套索 (L)")
        self.btn_tool_lasso.setCheckable(True)
        self.btn_tool_lasso.setToolTip("拖动画圈圈选保护区(Alt 减选)")
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        self._tool_group.addButton(self.btn_tool_eyedropper)
        self._tool_group.addButton(self.btn_tool_wand)
        self._tool_group.addButton(self.btn_tool_lasso)
        for b in (self.btn_tool_eyedropper, self.btn_tool_wand, self.btn_tool_lasso):
            g.addWidget(b)
        v.addWidget(gb_tool)

        # 已吸颜色
        gb_color = QGroupBox("已吸颜色")
        g = QVBoxLayout(gb_color)
        self.color_swatches_layout = QHBoxLayout()
        self.color_swatches_layout.setSpacing(4)
        self.color_swatches_layout.addStretch()
        g.addLayout(self.color_swatches_layout)
        self.btn_clear_colors = QPushButton("清空吸色")
        self.btn_clear_colors.clicked.connect(self._on_clear_colors)
        g.addWidget(self.btn_clear_colors)
        v.addWidget(gb_color)

        # 自动检测 / 清空保护
        self.btn_auto_detect = QPushButton("自动检测保护区 (A)")
        self.btn_auto_detect.setToolTip("检测透明背景 icon,自动把中心内容设为保护区")
        self.btn_auto_detect.clicked.connect(self._on_auto_detect)
        v.addWidget(self.btn_auto_detect)
        self.btn_clear_protect = QPushButton("清空保护区域")
        self.btn_clear_protect.clicked.connect(self._on_clear_protect)
        v.addWidget(self.btn_clear_protect)

        v.addStretch()
        return panel

    def _build_canvas_area(self) -> QWidget:
        wrap = QFrame()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.canvas, 1)
        # 底部状态
        bar = QHBoxLayout()
        self.lbl_status = QLabel("就绪")
        self.lbl_status.setStyleSheet("color:#888;")
        bar.addWidget(self.lbl_status)
        bar.addStretch()
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setStyleSheet("color:#888;")
        bar.addWidget(self.lbl_zoom)
        v.addLayout(bar)
        return wrap

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setFixedWidth(240)
        v = QVBoxLayout(panel)
        v.setSpacing(8)

        # 视图模式
        gb_view = QGroupBox("视图模式")
        g = QVBoxLayout(gb_view)
        self.rb_view_original = QRadioButton("原图")
        self.rb_view_result = QRadioButton("结果 (棋盘格)")
        self.rb_view_alpha = QRadioButton("Alpha 蒙版")
        self._view_group = QButtonGroup(self)
        self._view_group.setExclusive(True)
        self._view_group.addButton(self.rb_view_original)
        self._view_group.addButton(self.rb_view_result)
        self._view_group.addButton(self.rb_view_alpha)
        for r in (self.rb_view_original, self.rb_view_result, self.rb_view_alpha):
            g.addWidget(r)
        self.cb_show_protect = QCheckBox("显示保护区域叠加")
        self.cb_show_protect.setChecked(True)
        self.cb_show_protect.toggled.connect(self.canvas.set_show_protect)
        g.addWidget(self.cb_show_protect)
        v.addWidget(gb_view)

        # 参数
        gb_param = QGroupBox("参数")
        g = QGridLayout(gb_param)
        g.setColumnStretch(1, 1)

        g.addWidget(QLabel("容差:"), 0, 0)
        self.sl_tol = QSlider(Qt.Horizontal)
        self.sl_tol.setRange(0, 255)
        self.sl_tol.setValue(DEFAULT_TOLERANCE)
        self.lbl_tol = QLabel(str(DEFAULT_TOLERANCE))
        self.lbl_tol.setMinimumWidth(28)
        g.addWidget(self.sl_tol, 0, 1)
        g.addWidget(self.lbl_tol, 0, 2)

        g.addWidget(QLabel("羽化:"), 1, 0)
        self.sl_feather = QSlider(Qt.Horizontal)
        self.sl_feather.setRange(0, 8)
        self.sl_feather.setValue(DEFAULT_FEATHER)
        self.lbl_feather = QLabel(str(DEFAULT_FEATHER))
        self.lbl_feather.setMinimumWidth(28)
        g.addWidget(self.sl_feather, 1, 1)
        g.addWidget(self.lbl_feather, 1, 2)

        # 仅边缘扣色模式
        self.cb_edge_mode = QCheckBox("仅边缘扣色")
        self.cb_edge_mode.setToolTip("只扣图片边缘 N 像素内的命中色,保护中心主体")
        g.addWidget(self.cb_edge_mode, 2, 0, 1, 3)

        g.addWidget(QLabel("边缘宽:"), 3, 0)
        self.sl_edge = QSlider(Qt.Horizontal)
        self.sl_edge.setRange(1, 64)
        self.sl_edge.setValue(8)
        self.lbl_edge = QLabel("8")
        self.lbl_edge.setMinimumWidth(28)
        g.addWidget(self.sl_edge, 3, 1)
        g.addWidget(self.lbl_edge, 3, 2)

        v.addWidget(gb_param)

        # 操作
        gb_op = QGroupBox("操作")
        g = QVBoxLayout(gb_op)
        row = QHBoxLayout()
        self.btn_undo = QPushButton("撤销")
        self.btn_redo = QPushButton("重做")
        self.btn_undo.clicked.connect(self.canvas.undo)
        self.btn_redo.clicked.connect(self.canvas.redo)
        row.addWidget(self.btn_undo)
        row.addWidget(self.btn_redo)
        g.addLayout(row)
        self.btn_fit = QPushButton("适应窗口 (F)")
        self.btn_fit.clicked.connect(self._on_fit)
        g.addWidget(self.btn_fit)
        v.addWidget(gb_op)

        # 导出
        gb_export = QGroupBox("导出")
        g = QVBoxLayout(gb_export)
        self.btn_export = QPushButton("导出 PNG")
        self.btn_export.setStyleSheet(
            "QPushButton{background:#007acc;border-color:#007acc;font-weight:bold;}"
            "QPushButton:hover{background:#1a8ad4;}"
        )
        self.btn_export.clicked.connect(self._on_export)
        g.addWidget(self.btn_export)
        v.addWidget(gb_export)

        v.addStretch()
        return panel

    def _build_menu(self) -> None:
        mb = self.menuBar()
        m_file = mb.addMenu("文件")
        a_open = QAction("导入图片...", self)
        a_open.setShortcut(QKeySequence.Open)
        a_open.triggered.connect(self._on_open)
        a_export = QAction("导出 PNG...", self)
        a_export.setShortcut(QKeySequence.Save)
        a_export.triggered.connect(self._on_export)
        a_quit = QAction("退出", self)
        a_quit.setShortcut(QKeySequence.Quit)
        a_quit.triggered.connect(self.close)
        m_file.addAction(a_open)
        m_file.addAction(a_export)
        m_file.addSeparator()
        m_file.addAction(a_quit)

        m_edit = mb.addMenu("编辑")
        a_undo = QAction("撤销", self)
        a_undo.setShortcut(QKeySequence.Undo)
        a_undo.triggered.connect(self.canvas.undo)
        a_redo = QAction("重做", self)
        a_redo.setShortcut(QKeySequence.Redo)
        a_redo.triggered.connect(self.canvas.redo)
        m_edit.addAction(a_undo)
        m_edit.addAction(a_redo)

        m_view = mb.addMenu("视图")
        a_fit = QAction("适应窗口", self)
        a_fit.setShortcut(QKeySequence("F"))
        a_fit.triggered.connect(self._on_fit)
        m_view.addAction(a_fit)

    # ---------- 信号连接 ----------

    def _connect_signals(self) -> None:
        self.canvas.color_picked.connect(self._on_color_picked)
        self.canvas.image_loaded.connect(self._on_image_loaded)
        self.canvas.mask_changed.connect(self._on_mask_changed)
        self.canvas.cursor_pixel.connect(self._on_cursor_pixel)

        self.btn_tool_eyedropper.clicked.connect(lambda: self._set_tool(Tool.EYEDROPPER))
        self.btn_tool_wand.clicked.connect(lambda: self._set_tool(Tool.WAND))
        self.btn_tool_lasso.clicked.connect(lambda: self._set_tool(Tool.LASSO))

        self.rb_view_original.clicked.connect(lambda: self._set_view(ViewMode.ORIGINAL))
        self.rb_view_result.clicked.connect(lambda: self._set_view(ViewMode.RESULT))
        self.rb_view_alpha.clicked.connect(lambda: self._set_view(ViewMode.ALPHA))

        self.sl_tol.valueChanged.connect(self._on_tol_changed)
        self.sl_feather.valueChanged.connect(self._on_feather_changed)
        self.cb_edge_mode.toggled.connect(self.canvas.set_edge_mode)
        self.sl_edge.valueChanged.connect(self._on_edge_changed)

    # ---------- 槽 ----------

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self.canvas.load_image_path(path)

    def _on_image_loaded(self, path: str) -> None:
        name = path.split('/')[-1].split(chr(92))[-1]
        self.lbl_status.setText(f"已加载: {name}")
        self._refresh_zoom_label()
        # 加载后自动尝试检测透明背景 icon 的保护区
        if self.canvas.auto_detect_protect():
            self.lbl_status.setText(f"已加载: {name}  (已自动检测保护区)")
            self._refresh_undo_state()

    def _on_auto_detect(self) -> None:
        if not self.canvas.has_image():
            QMessageBox.information(self, "自动检测", "请先导入图片。")
            return
        ok = self.canvas.auto_detect_protect()
        if ok:
            self.lbl_status.setText("已自动检测保护区(透明背景 icon)")
        else:
            self.lbl_status.setText("未检测到透明背景,无法自动设保护区")
        self._refresh_undo_state()

    def _on_color_picked(self, rgb: tuple[int, int, int]) -> None:
        # canvas 内部已加入选区,这里只刷新色块 UI
        self._refresh_swatches()
        self.lbl_status.setText(f"吸色: RGB{rgb}")

    def _on_clear_colors(self) -> None:
        self.canvas.clear_picked_colors()
        self._refresh_swatches()

    def _on_clear_protect(self) -> None:
        self.canvas.clear_protect()
        self.lbl_status.setText("已清空保护区域")

    def _on_tol_changed(self, v: int) -> None:
        self.lbl_tol.setText(str(v))
        self.canvas.set_tolerance(v)

    def _on_feather_changed(self, v: int) -> None:
        self.lbl_feather.setText(str(v))
        self.canvas.set_feather(v)

    def _on_edge_changed(self, v: int) -> None:
        self.lbl_edge.setText(str(v))
        self.canvas.set_edge_width(v)

    def _on_mask_changed(self) -> None:
        self._refresh_undo_state()

    def _on_cursor_pixel(self, rgb: tuple[int, int, int]) -> None:
        # 不覆盖重要状态,只轻微提示
        pass

    def _on_fit(self) -> None:
        # 重新触发 fit
        if self.canvas.has_image():
            self.canvas._fit_to_view()
            self.canvas.update()
            self._refresh_zoom_label()

    def _on_export(self) -> None:
        if not self.canvas.has_image():
            QMessageBox.information(self, "导出", "请先导入图片。")
            return
        result = self.canvas.get_result_rgba()
        if result is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 PNG", "icon_cut.png", "PNG (*.png)"
        )
        if path:
            try:
                ip.export_png(result, path)
                self.lbl_status.setText(f"已导出: {path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    # ---------- 辅助 ----------

    def _set_tool(self, tool: Tool) -> None:
        self.canvas.set_tool(tool)
        mapping = {
            Tool.EYEDROPPER: self.btn_tool_eyedropper,
            Tool.WAND: self.btn_tool_wand,
            Tool.LASSO: self.btn_tool_lasso,
        }
        mapping[tool].setChecked(True)

    def _set_view(self, mode: ViewMode) -> None:
        self.canvas.set_view_mode(mode)
        mapping = {
            ViewMode.ORIGINAL: self.rb_view_original,
            ViewMode.RESULT: self.rb_view_result,
            ViewMode.ALPHA: self.rb_view_alpha,
        }
        mapping[mode].setChecked(True)

    def _refresh_swatches(self) -> None:
        # 清空
        while self.color_swatches_layout.count() > 1:
            item = self.color_swatches_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for rgb in self.canvas.get_picked_colors():
            sw = ColorSwatch(rgb, self._remove_color)
            self.color_swatches_layout.insertWidget(self.color_swatches_layout.count() - 1, sw)

    def _remove_color(self, rgb: tuple[int, int, int]) -> None:
        self.canvas.remove_picked_color(rgb)
        self._refresh_swatches()

    def _refresh_undo_state(self) -> None:
        self.btn_undo.setEnabled(self.canvas.can_undo())
        self.btn_redo.setEnabled(self.canvas.can_redo())

    def _refresh_zoom_label(self) -> None:
        self.lbl_zoom.setText(f"{int(self.canvas.get_zoom() * 100)}%")

    # ---------- 快捷键 ----------

    def keyPressEvent(self, e) -> None:
        key = e.key()
        mod = e.modifiers()
        if mod == Qt.NoModifier:
            if key == Qt.Key_E:
                self._set_tool(Tool.EYEDROPPER); return
            if key == Qt.Key_W:
                self._set_tool(Tool.WAND); return
            if key == Qt.Key_L:
                self._set_tool(Tool.LASSO); return
            if key == Qt.Key_F:
                self._on_fit(); return
            if key == Qt.Key_A:
                self._on_auto_detect(); return
            if key == Qt.Key_1:
                self._set_view(ViewMode.ORIGINAL); return
            if key == Qt.Key_2:
                self._set_view(ViewMode.RESULT); return
            if key == Qt.Key_3:
                self._set_view(ViewMode.ALPHA); return
        # Ctrl+Z / Ctrl+Y
        if mod & Qt.ControlModifier:
            if key == Qt.Key_Z:
                self.canvas.undo(); return
            if key == Qt.Key_Y:
                self.canvas.redo(); return
        super().keyPressEvent(e)
