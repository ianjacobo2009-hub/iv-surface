"""Draws the app icon (dark rounded square with a 3D volatility smile wireframe) as PNG + macOS .icns.
Run: python tools/make_icon.py   (writes assets/icon.png and assets/icon.icns)"""
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen

OUT = Path(__file__).resolve().parent.parent / "assets"


def draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    m = size * 0.06
    r = QRectF(m, m, size - 2 * m, size - 2 * m)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, QColor("#0d1b2e"))
    g.setColorAt(1, QColor("#06080b"))
    bg = QPainterPath()
    bg.addRoundedRect(r, size * 0.22, size * 0.22)
    p.fillPath(bg, g)
    # five smiles stacked in depth: back ones higher and narrower, coloured like the surface scale
    colors = ["#123f73", "#1d6f8c", "#2a9d8f", "#e9c46a", "#e76f51"]
    s = size
    for i, c in enumerate(colors):
        depth = i / (len(colors) - 1)
        y0 = s * (0.36 + 0.30 * depth)
        x0, x1 = s * (0.30 - 0.08 * depth), s * (0.70 + 0.08 * depth)
        curve = QPainterPath(QPointF(x0, y0 - s * 0.14))
        curve.quadTo(QPointF((x0 + x1) / 2, y0 + s * 0.12), QPointF(x1, y0 - s * 0.08))
        pen = QPen(QColor(c), s * (0.03 + 0.012 * depth))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawPath(curve)
    p.end()
    return img


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    draw(1024).save(str(OUT / "icon.png"))
    if sys.platform == "darwin":
        with tempfile.TemporaryDirectory() as d:
            iset = Path(d) / "icon.iconset"
            iset.mkdir()
            for n in (16, 32, 128, 256, 512):
                draw(n).save(str(iset / f"icon_{n}x{n}.png"))
                draw(n * 2).save(str(iset / f"icon_{n}x{n}@2x.png"))
            subprocess.run(["iconutil", "-c", "icns", str(iset), "-o", str(OUT / "icon.icns")], check=True)
    draw(256).save(str(OUT / "icon.ico"))
    print("ok", OUT)
