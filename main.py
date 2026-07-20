"""iconCut 入口."""
import os
import sys

from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import QApplication, QFileIconProvider
from PySide6.QtCore import QFileInfo

from app.main_window import MainWindow


def resource_path(*parts: str) -> str:
    """资源绝对路径,兼容 PyInstaller 打包(单文件)与开发环境."""
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("iconCut")
    app.setOrganizationName("MMY")

    # 应用图标:
    # - exe 文件图标由 PyInstaller --icon 决定(资源管理器/任务栏一致)
    # - 窗体左上角图标用打包的 PNG(高清);若资源缺失则回退到 exe 内嵌图标,保证三者一致
    icon_path = resource_path("图标", "MMY-AI-Studio-icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        app.setWindowIcon(QFileIconProvider().icon(QFileInfo(sys.executable)))

    # 统一字体
    f = QFont()
    f.setFamilies(["Microsoft YaHei", "PingFang SC", "Segoe UI", "Arial"])
    f.setPointSize(10)
    app.setFont(f)

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
