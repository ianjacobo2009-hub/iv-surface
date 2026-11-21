# PyInstaller spec: builds IV Surface.app (macOS) or IV Surface.exe (Windows)
import sys
from PyInstaller.utils.hooks import collect_data_files
a = Analysis(["run_ivsurface.py"], pathex=["."], datas=[("assets", "assets")] + collect_data_files("plotly"),
             hiddenimports=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "scipy.special._cdflib"],
             excludes=["tkinter", "matplotlib", "IPython", "pytest"])
pyz = PYZ(a.pure)
icon = "assets/icon.icns" if sys.platform == "darwin" else "assets/icon.ico"
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="IV Surface", console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="IV Surface")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="IV Surface.app", icon=icon, bundle_identifier="com.ianjacobo.ivsurface",
                 info_plist={"CFBundleShortVersionString": "1.4.0", "NSHighResolutionCapable": True})
