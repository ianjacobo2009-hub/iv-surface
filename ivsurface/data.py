"""Download option chains with yfinance and compute an implied volatility for every usable quote."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from .bs import implied_vol

MIN_DAYS, MAX_DAYS = 10, 550        # skip very short expiries (noisy) and the far LEAPS
MONEYNESS = (0.75, 1.25)           # strikes between 75% and 125% of spot
MAX_REL_SPREAD = 0.35              # (ask - bid) / mid: drop quotes that are too wide to trust


def risk_free_rate() -> float:
    """13-week T-bill yield (^IRX, quoted in percent) as a continuously compounded rate."""
    try:
        y = yf.Ticker("^IRX").history(period="5d")["Close"].dropna().iloc[-1] / 100
        return float(np.log(1 + y))
    except Exception:
        return 0.04


def dividend_yield(tk: yf.Ticker, spot: float) -> float:
    """Trailing 12-month dividends ÷ spot, used as the continuous yield q. 0 if the stock pays none."""
    try:
        d = tk.dividends
        if d.empty:
            return 0.0
        cutoff = d.index.max() - pd.Timedelta(days=365)
        return float(np.log(1 + d[d.index > cutoff].sum() / spot))
    except Exception:
        return 0.0


def fetch(ticker: str, cache_dir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    tk = yf.Ticker(ticker)
    spot = float(tk.fast_info["last_price"])
    r, q = risk_free_rate(), dividend_yield(tk, spot)
    now = datetime.now(timezone.utc)
    rows = []
    for exp in tk.options:
        expiry = pd.Timestamp(exp + " 21:00", tz="UTC")      # 4:00 pm New York close
        days = (expiry - now).total_seconds() / 86400
        if not (MIN_DAYS <= days <= MAX_DAYS):
            continue
        chain = tk.option_chain(exp)
        for kind, df in (("call", chain.calls), ("put", chain.puts)):
            df = df.assign(kind=kind, expiry=exp, days=days)
            rows.append(df[["contractSymbol", "strike", "bid", "ask", "lastPrice", "volume", "openInterest",
                            "impliedVolatility", "kind", "expiry", "days"]])
    if not rows:
        raise SystemExit(f"No option expiries found for {ticker}")
    raw = pd.concat(rows, ignore_index=True).rename(columns={"impliedVolatility": "yahoo_iv"})
    meta = dict(ticker=ticker.upper(), spot=spot, r=r, q=q, asof=now.strftime("%Y-%m-%d %H:%M UTC"),
                n_expiries=raw.expiry.nunique(), n_raw=len(raw))
    df = clean(raw, spot)
    T = df.days / 365.0
    df["iv"] = [implied_vol(m, spot, k, t, r, q, kd) for m, k, t, kd in zip(df.mid, df.strike, T, df.kind)]
    df = df.dropna(subset=["iv"])
    df = df[(df.iv > 0.01) & (df.iv < 3.0)]
    meta["n_used"] = len(df)
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        stamp = now.strftime("%Y%m%d_%H%M")
        df.to_csv(cache_dir / f"{ticker.upper()}_{stamp}_iv.csv", index=False)
        pd.Series(meta).to_json(cache_dir / f"{ticker.upper()}_{stamp}_meta.json")
    return df, meta


def clean(raw: pd.DataFrame, spot: float) -> pd.DataFrame:
    """Keep liquid out-of-the-money quotes: puts below spot, calls at or above it.

    OTM options carry almost all their value as time value, so their prices pin down volatility best. Deep ITM
    prices are mostly intrinsic value plus a wide spread, which makes the implied vol noisy.
    """
    df = raw[(raw.bid > 0) & (raw.ask > raw.bid)].copy()
    df["mid"] = (df.bid + df.ask) / 2
    df = df[(df.ask - df.bid) / df.mid <= MAX_REL_SPREAD]
    df["moneyness"] = df.strike / spot
    df = df[df.moneyness.between(*MONEYNESS)]
    otm = ((df.kind == "put") & (df.strike < spot)) | ((df.kind == "call") & (df.strike >= spot))
    df = df[otm & ((df.openInterest.fillna(0) > 0) | (df.volume.fillna(0) > 0))]
    return df.reset_index(drop=True)
