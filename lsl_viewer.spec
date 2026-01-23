# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for stream-viewer main application (lsl_viewer)
"""

import sys
from pathlib import Path

# Get the project root directory (where the spec file is located)
# SPECPATH is set by PyInstaller to the path of the spec file
try:
    spec_path = Path(SPECPATH)
    project_root = spec_path.parent
except NameError:
    # Fallback: use current working directory (should be project root when running build script)
    import os
    project_root = Path(os.getcwd())

block_cipher = None

# Helper function to ensure paths exist
def get_data_path(*path_parts, target_dir):
    """Get absolute path and verify it exists."""
    abs_path = project_root.joinpath(*path_parts)
    if not abs_path.exists():
        raise FileNotFoundError(f"Data file not found: {abs_path}")
    return (str(abs_path), target_dir)

# Collect all data files
datas = [
    # QML files
    get_data_path('stream_viewer', 'qml', 'streamInfoListView.qml', target_dir='stream_viewer/qml'),
    # Icons
    get_data_path('icons', 'stream_viewer icon_no_bg2.ico', target_dir='icons'),
    get_data_path('icons', 'stream_viewer icon_no_bg2.png', target_dir='icons'),
]

# Hidden imports - modules that PyInstaller might not automatically detect
hiddenimports = [
    # PyQt5/QML
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtQuick',
    'PyQt5.QtQml',
    'PyQt5.QtQuick.Controls',
    'PyQt5.QtQuick.Layouts',
    # QtPy compatibility layer
    'qtpy',
    'qtpy.QtCore',
    'qtpy.QtGui',
    'qtpy.QtWidgets',
    'qtpy.QtQuick',
    # Stream viewer modules
    'stream_viewer',
    'stream_viewer.data',
    'stream_viewer.widgets',
    'stream_viewer.renderers',
    'stream_viewer.applications',
    'stream_viewer.buffers',
    'stream_viewer.utils',
    # External dependencies that might need explicit inclusion
    'pylsl',
    'numpy',
    'scipy',
    'matplotlib',
    'pandas',
    'pyqtgraph',
    'vispy',
    'visbrain',
    'mne',
    'eegsynth',
    'sounddevice',
    'python_rtmidi',
    'redis',
    'Levenshtein',
    'pyaudio',
    'slimgui',
    'ipykernel',
    'ipywidgets',
    'dearpygui',
    'pyvista',
    'pyvistaqt',
    'phopymnehelper',
    'phopyqthelper',
    # Additional Qt modules
    'PyQt5.sip',
]

a = Analysis(
    ['stream_viewer/applications/main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='lsl_viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging, False for windowed app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'icons' / 'stream_viewer icon_no_bg2.ico') if sys.platform == 'win32' else None,
)
