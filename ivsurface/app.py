"""Desktop app: type a ticker, build the implied volatility surface, and explore it inside the window."""
from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
                               QPushButton, QVBoxLayout, QWidget)

from .data import fetch
from .plot import dashboard

HOME = Path.home() / "Documents" / "IV Surface"     # writable for the packaged app too
DATA, OUTPUT = HOME / "data", HOME / "output"
ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "assets"
QUICK = ["SPY", "QQQ", "AAPL", "NVDA", "TSLA"]

STYLE = """
QWidget { background:#06080b; color:#d7dde8; font-family:Inter, -apple-system, 'Segoe UI', sans-serif; font-size:13px; }
#bar { background:#0d1117; border-bottom:1px solid #1b2230; }
QLineEdit { background:#06080b; border:1px solid #1b2230; border-radius:6px; padding:7px 10px;
            font-family:'JetBrains Mono', Menlo, Consolas, monospace; font-size:14px; min-width:110px; }
QLineEdit:focus { border-color:#4cc9f0; }
QPushButton { background:#0d1117; border:1px solid #1b2230; border-radius:6px; padding:7px 12px; }
QPushButton:hover { border-color:#4cc9f0; }
QPushButton:disabled { color:#4a5263; }
#build { background:#4cc9f0; color:#06080b; border:none; font-weight:700; padding:8px 16px; }
#build:disabled { background:#1d6f8c; color:#06080b; }
#quick { color:#7d8799; font-family:'JetBrains Mono', Menlo, Consolas, monospace; padding:6px 9px; }
#status { color:#7d8799; font-family:'JetBrains Mono', Menlo, Consolas, monospace; font-size:12px; }
"""

WELCOME = """<!doctype html><html><body style="margin:0;background:#06080b;color:#d7dde8;
font-family:Inter,-apple-system,'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
<div style="max-width:560px;text-align:center;line-height:1.6">
<h1 style="font-size:26px;margin:0 0 8px"><span style="color:#4cc9f0">Implied Volatility</span> Surface</h1>
<p style="color:#7d8799;margin:0 0 18px">Type a ticker above and press <b style="color:#d7dde8">Build surface</b>.
The app downloads every option chain, backs out Black-Scholes implied volatility for each quote and draws a
rotating 3D strike × expiry × IV surface with the term structure, smiles and skew.</p>
<p style="color:#7d8799;font-size:12px">Data: Yahoo Finance (delayed). For study, not trading.</p>
</div></body></html>"""


class Worker(QObject):
    done = Signal(str, str)      # html path, summary
    failed = Signal(str)

    def __init__(self, ticker: str = "", csv: Path | None = None):
        super().__init__()
        self.ticker, self.csv = ticker, csv

    def run(self):
        try:
            if self.csv:
                df = pd.read_csv(self.csv)
                meta = json.loads(Path(str(self.csv).replace("_iv.csv", "_meta.json")).read_text())
            else:
                df, meta = fetch(self.ticker, DATA)
            if df.empty:
                raise ValueError("no usable option quotes")
            out = dashboard(df, meta, OUTPUT / f"{meta['ticker']}_iv_surface.html")
            self.done.emit(str(out), f"{meta['ticker']} · spot {meta['spot']:,.2f} · {meta['n_used']:,} quotes · "
                                     f"{df.expiry.nunique()} expiries · as of {meta['asof']}")
        except BaseException as e:          # fetch() raises SystemExit when a ticker has no options
            what = f"no option data for {self.ticker}" if self.ticker else "snapshot could not be read"
            self.failed.emit(f"{what} ({str(e) or e.__class__.__name__})")


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IV Surface")
        self.resize(1440, 920)
        self.current: str | None = None
        self.thread: QThread | None = None

        bar = QWidget(objectName="bar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 10, 16, 10)
        self.ticker = QLineEdit("SPY", placeholderText="Ticker")
        self.ticker.returnPressed.connect(self.build)
        self.build_btn = QPushButton("Build surface", objectName="build")
        self.build_btn.clicked.connect(self.build)
        row.addWidget(self.ticker)
        row.addWidget(self.build_btn)
        for t in QUICK:
            b = QPushButton(t, objectName="quick")
            b.clicked.connect(lambda _=False, t=t: (self.ticker.setText(t), self.build()))
            row.addWidget(b)
        row.addSpacing(12)
        self.status = QLabel("Ready", objectName="status")
        row.addWidget(self.status, 1)
        self.snap_btn = QPushButton("Open snapshot…")
        self.snap_btn.clicked.connect(self.open_snapshot)
        self.browser_btn = QPushButton("Open in browser")
        self.browser_btn.setEnabled(False)
        self.browser_btn.clicked.connect(lambda: webbrowser.open(Path(self.current).as_uri()))
        row.addWidget(self.snap_btn)
        row.addWidget(self.browser_btn)

        self.view = QWebEngineView()
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)   # Google Fonts
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.view.setHtml(WELCOME)

        root = QWidget()
        col = QVBoxLayout(root)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(bar)
        col.addWidget(self.view, 1)
        self.setCentralWidget(root)

    def _start(self, worker: Worker, msg: str):
        if self.thread and self.thread.isRunning():
            return
        self.build_btn.setEnabled(False)
        self.snap_btn.setEnabled(False)
        self.status.setText(msg)
        self.thread = QThread()
        self.worker = worker
        worker.moveToThread(self.thread)
        self.thread.started.connect(worker.run)
        worker.done.connect(self._done)
        worker.failed.connect(self._failed)
        worker.done.connect(self.thread.quit)
        worker.failed.connect(self.thread.quit)
        self.thread.start()

    def build(self):
        t = self.ticker.text().strip().upper()
        if t:
            self._start(Worker(ticker=t), f"Downloading {t} option chains and solving implied vols… (about 10-40 s)")

    def open_snapshot(self):
        DATA.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Open a saved snapshot", str(DATA), "Snapshots (*_iv.csv)")
        if path:
            self._start(Worker(csv=Path(path)), f"Redrawing {Path(path).name}…")

    def _done(self, path: str, summary: str):
        self.current = path
        self.view.load(QUrl.fromLocalFile(path))
        self.status.setText(summary)
        self.browser_btn.setEnabled(True)
        self.build_btn.setEnabled(True)
        self.snap_btn.setEnabled(True)

    def _failed(self, err: str):
        self.status.setText(f"Could not build: {err}")
        self.build_btn.setEnabled(True)
        self.snap_btn.setEnabled(True)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("IV Surface")
    icon = ASSETS / "icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    app.setStyleSheet(STYLE)
    w = Window()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
