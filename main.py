"""Точка входа калькулятора падения напряжения PoE."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_API", "pyside6")


def main() -> int:
    from PySide6.QtCore import QLocale
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from data import APP_TITLE, APP_VERSION, APPLICATION_ID, ORGANIZATION
    from gui.main_window import MainWindow

    QLocale.setDefault(QLocale(QLocale.Language.Russian))
    app = QApplication(sys.argv)
    app.setOrganizationName(ORGANIZATION)
    app.setApplicationName(APPLICATION_ID)
    app.setApplicationVersion(APP_VERSION)
    app.setApplicationDisplayName(APP_TITLE)
    font = QFont()
    font.setFamilies(["Noto Sans", "Segoe UI", "Ubuntu", "DejaVu Sans"])
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.resize(1200, 860)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
