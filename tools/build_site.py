"""Build the website (GitHub Pages): one live dashboard per ticker plus a landing page.

    python tools/build_site.py                 # live data, writes site/
    python tools/build_site.py --offline       # redraw the saved snapshots in samples/ (no internet)

If Yahoo fails for a ticker, the latest snapshot in samples/ is used so the site always builds.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ivsurface.data import fetch  # noqa: E402
from ivsurface.plot import ACCENT, BG, GRID_C, MUTED, PANEL, TEXT, dashboard  # noqa: E402
from ivsurface.surface import atm_term_structure  # noqa: E402

TICKERS = ["SPY", "QQQ", "AAPL", "NVDA", "TSLA"]
SAMPLES = ROOT / "samples"
REPO = "https://github.com/ianjacobo2009-hub/iv-surface"


def snapshot(ticker: str):
    files = sorted(SAMPLES.glob(f"{ticker}_*_iv.csv"))
    if not files:
        return None
    meta = json.loads(Path(str(files[-1]).replace("_iv.csv", "_meta.json")).read_text())
    return pd.read_csv(files[-1]), meta


def load(ticker: str, offline: bool):
    if not offline:
        try:
            df, meta = fetch(ticker)
            if len(df) >= 50:
                return df, meta, "live"
        except Exception as e:  # Yahoo blocks or rate-limits sometimes
            print(f"  {ticker}: live download failed ({e}); using snapshot")
    snap = snapshot(ticker)
    return (*snap, "snapshot") if snap else None


def card(t: str, meta: dict, df: pd.DataFrame, src: str) -> str:
    ts = atm_term_structure(df, meta["spot"])
    atm30 = float(np.interp(30, ts.days, ts.atm_iv)) if len(ts) else float("nan")
    atm365 = float(np.interp(365, ts.days, ts.atm_iv)) if len(ts) else float("nan")
    shape = "inverted" if atm30 > atm365 else "upward"
    return (f"<a class='card' href='{t.lower()}.html'><div class='t'>{html.escape(t)}</div>"
            f"<div class='kv'><span>Spot</span><b>{meta['spot']:,.2f}</b></div>"
            f"<div class='kv'><span>ATM IV 30d</span><b>{atm30:.1%}</b></div>"
            f"<div class='kv'><span>ATM IV 1y</span><b>{atm365:.1%}</b></div>"
            f"<div class='kv'><span>Term structure</span><b>{shape}</b></div>"
            f"<div class='foot'>{meta['n_used']:,} quotes · {html.escape(meta['asof'])}"
            f"{'' if src == 'live' else ' · saved snapshot'}</div></a>")


def landing(cards: list[str]) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Implied Volatility Surface</title>
<meta name="description" content="Rotating 3D implied volatility surfaces from live option chains (Black-Scholes, Brent's method).">
<meta property="og:title" content="Implied Volatility Surface">
<meta property="og:description" content="Rotating 3D implied volatility surfaces for SPY, QQQ, AAPL, NVDA and TSLA, built from live option chains with Black-Scholes. Rebuilt every weekday.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://ianjacobo2009-hub.github.io/iv-surface/">
<meta property="og:image" content="https://raw.githubusercontent.com/ianjacobo2009-hub/iv-surface/main/docs/spy_surface.jpg">
<meta property="og:image:width" content="1440">
<meta property="og:image:height" content="778">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:{BG}; color:{TEXT}; font-family:Inter,-apple-system,'Segoe UI',sans-serif; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:48px 16px 32px; }}
  h1 {{ margin:0 0 10px; font-size:34px; letter-spacing:.2px; }} h1 em {{ font-style:normal; color:{ACCENT}; }}
  p {{ color:{MUTED}; line-height:1.65; max-width:720px; margin:0 0 14px; }}
  .mono {{ font-family:'JetBrains Mono',Menlo,monospace; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); gap:14px; margin:30px 0; }}
  .card {{ display:block; background:{PANEL}; border:1px solid {GRID_C}; border-radius:12px; padding:16px; color:{TEXT};
          text-decoration:none; transition:border-color .15s, transform .15s; }}
  .card:hover {{ border-color:{ACCENT}; transform:translateY(-2px); }}
  .t {{ font:700 22px 'JetBrains Mono',Menlo,monospace; color:{ACCENT}; margin-bottom:10px; }}
  .kv {{ display:flex; justify-content:space-between; font-size:13px; padding:3px 0; }} .kv span {{ color:{MUTED}; }}
  .kv b {{ font-family:'JetBrains Mono',Menlo,monospace; font-weight:600; }}
  .foot {{ color:{MUTED}; font-size:10.5px; margin-top:10px; font-family:'JetBrains Mono',Menlo,monospace; }}
  .links a {{ color:{TEXT}; border:1px solid {GRID_C}; border-radius:8px; padding:9px 14px; text-decoration:none;
             display:inline-block; margin:0 8px 8px 0; font-size:13px; }}
  .links a:hover {{ border-color:{ACCENT}; }} .links a.primary {{ background:{ACCENT}; color:{BG}; border-color:{ACCENT}; font-weight:700; }}
  footer {{ color:{MUTED}; font-size:11.5px; line-height:1.6; border-top:1px solid {GRID_C}; padding-top:16px; }}
</style></head><body><div class="wrap">
<h1><em>Implied Volatility</em> Surface</h1>
<p>Every listed option for a ticker, from 10 days to about 18 months out. For each out-of-the-money quote the site finds the
volatility σ where the Black-Scholes-Merton price equals the market mid price (Brent's method), then draws a rotating
3D strike × expiry × IV surface with the ATM term structure, volatility smiles and put skew.</p>
<p class="mono" style="font-size:12px">Rebuilt from Yahoo Finance option chains every weekday after the US close.</p>
<div class="grid">{''.join(cards)}</div>
<div class="links"><a class="primary" href="{REPO}/releases/latest">Download the desktop app (any ticker)</a><a href="{REPO}">Source code</a></div>
<footer>Data: Yahoo Finance via yfinance, delayed. For study, not trading. r = 13-week T-bill (^IRX), q = trailing dividend yield.
Reference: J. Hull, <i>Options, Futures, and Other Derivatives</i>, ch. 15, 17 and 20. A personal project by Ian.</footer>
</div></body></html>"""


def build(out: Path, offline: bool = False, tickers: list[str] = TICKERS) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    cards, built = [], []
    for t in tickers:
        print(f"{t}…")
        got = load(t, offline)
        if not got:
            print(f"  {t}: no data, skipped")
            continue
        df, meta, src = got
        dashboard(df, meta, out / f"{t.lower()}.html", plotlyjs="cdn", back="index.html")
        cards.append(card(t, meta, df, src))
        built.append(t)
        print(f"  {t}: {meta['n_used']} quotes ({src})")
    (out / "index.html").write_text(landing(cards), encoding="utf-8")
    (out / ".nojekyll").write_text("")
    return built


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--out", type=Path, default=ROOT / "site")
    a.add_argument("--offline", action="store_true")
    args = a.parse_args()
    if not build(args.out, args.offline):
        sys.exit("No ticker could be built")
