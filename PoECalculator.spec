# -*- mode: python ; coding: utf-8 -*-
"""Сборка одного файла калькулятора. Анализ импортов один и тот же на обеих ОС."""

from PyInstaller.utils.hooks import collect_submodules
import sys

hidden = collect_submodules("gui")
hidden += [
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_agg",
    "csv",
    "json",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tests", "tkinter", "pdb", "doctest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PoECalculator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None if sys.platform != "win32" else "icon.ico",
)
