"""Turn scattered (strike, expiry, IV) points into a smooth grid for a 3D surface."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter


def grid(df: pd.DataFrame, spot: float, nk: int = 90, nt: int = 60, smooth: float = 1.8):
    """Interpolate IV onto a regular strike × days grid.

    The interpolation runs in (log-moneyness, √T), where smiles are close to straight lines, and the result is
    mapped back to strikes and days for the axes. Cells outside the quoted region stay empty (NaN) so the surface
    never shows data that doesn't exist. A light Gaussian blur that ignores empty cells removes quote noise.
    """
    x = np.log(df.strike.values / spot)
    y = np.sqrt(df.days.values / 365)
    z = df.iv.values
    xs = np.linspace(np.percentile(x, 1), np.percentile(x, 99), nk)
    ys = np.linspace(y.min(), y.max(), nt)
    X, Y = np.meshgrid(xs, ys)
    Z = griddata((x, y), z, (X, Y), method="linear")
    if smooth:
        mask = ~np.isnan(Z)
        num = gaussian_filter(np.where(mask, Z, 0.0), smooth)
        den = gaussian_filter(mask.astype(float), smooth)
        with np.errstate(invalid="ignore", divide="ignore"):
            Z = np.where(mask, num / den, np.nan)
    strikes = spot * np.exp(xs)
    days = (ys ** 2) * 365
    return strikes, days, Z


def atm_term_structure(df: pd.DataFrame, spot: float) -> pd.DataFrame:
    """At-the-money IV for each expiry: linear interpolation of the smile at K = spot."""
    out = []
    for exp, g in df.groupby("expiry"):
        g = g.sort_values("strike")
        if g.strike.min() < spot < g.strike.max():
            out.append(dict(expiry=exp, days=g.days.iloc[0], atm_iv=np.interp(spot, g.strike, g.iv)))
    return pd.DataFrame(out).sort_values("days")


def skew_25(df: pd.DataFrame, spot: float) -> pd.DataFrame:
    """A simple skew measure per expiry: IV at 90% of spot minus IV at 110% of spot."""
    out = []
    for exp, g in df.groupby("expiry"):
        g = g.sort_values("strike")
        if g.strike.min() < 0.9 * spot and g.strike.max() > 1.1 * spot:
            out.append(dict(expiry=exp, days=g.days.iloc[0],
                            skew_val=np.interp(0.9 * spot, g.strike, g.iv) - np.interp(1.1 * spot, g.strike, g.iv)))
    return pd.DataFrame(out).sort_values("days")
