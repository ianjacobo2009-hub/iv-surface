"""python -m ivsurface SPY [--open] [--from-csv path]"""
import argparse
import json
import webbrowser
from pathlib import Path

import pandas as pd

from .data import fetch
from .plot import dashboard

ROOT = Path(__file__).resolve().parent.parent


def main():
    p = argparse.ArgumentParser(description="Implied volatility surface from live option chains")
    p.add_argument("ticker", nargs="?", default="SPY")
    p.add_argument("--open", action="store_true", help="open the dashboard in the browser")
    p.add_argument("--from-csv", type=Path, help="re-draw from a saved *_iv.csv instead of downloading")
    a = p.parse_args()
    if a.from_csv:
        df = pd.read_csv(a.from_csv)
        meta = json.loads(Path(str(a.from_csv).replace("_iv.csv", "_meta.json")).read_text())
    else:
        print(f"Downloading {a.ticker.upper()} option chains…")
        df, meta = fetch(a.ticker, ROOT / "data")
    print(f"{meta['n_used']} quotes with an implied vol across {df.expiry.nunique()} expiries (spot {meta['spot']:.2f}, "
          f"r {meta['r']:.2%}, q {meta['q']:.2%})")
    out = dashboard(df, meta, ROOT / "output" / f"{meta['ticker']}_iv_surface.html")
    print("Saved", out)
    if a.open:
        webbrowser.open(out.as_uri())


if __name__ == "__main__":
    main()
