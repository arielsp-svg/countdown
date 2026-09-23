# PyInstaller build. One file, no console window, no installer (R13).
# Run on Windows:  pyinstaller --clean --noconfirm Countdown.spec
block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=["openpyxl", "openpyxl.cell._writer"],
    hookspath=[],
    runtime_hooks=[],
    # Trim what the app never touches, so the single .exe stays small.
    excludes=[
        # Note: email and http are NOT excluded - urllib.request needs both.
        "numpy", "pandas", "matplotlib", "scipy", "PIL", "pytest",
        "test", "unittest", "doctest", "pydoc",
        "xmlrpc", "sqlite3", "distutils", "setuptools", "pip",
    ],
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
    name="Countdown",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # R12: nothing visible unless an alert is due
    disable_windowed_traceback=True,
    icon=None,
    version=None,
)
