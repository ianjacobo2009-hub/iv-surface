import math

import numpy as np
import pandas as pd
import pytest

from ivsurface.bs import bounds, implied_vol, price, vega
from ivsurface.surface import grid


def test_hull_example():
    # Hull, Example 15.6: S=42, K=40, r=10%, σ=20%, T=0.5 → call 4.76, put 0.81
    assert price(42, 40, 0.5, 0.10, 0, 0.2, "call") == pytest.approx(4.76, abs=0.01)
    assert price(42, 40, 0.5, 0.10, 0, 0.2, "put") == pytest.approx(0.81, abs=0.01)


def test_put_call_parity_with_dividends():
    S, K, T, r, q, s = 750, 700, 0.75, 0.04, 0.012, 0.22
    c, p = price(S, K, T, r, q, s, "call"), price(S, K, T, r, q, s, "put")
    assert c - p == pytest.approx(S * math.exp(-q * T) - K * math.exp(-r * T), abs=1e-9)


@pytest.mark.parametrize("sigma", [0.05, 0.15, 0.4, 1.2])
@pytest.mark.parametrize("kind,K", [("call", 800), ("put", 650), ("call", 750)])
def test_iv_round_trip(sigma, kind, K):
    S, T, r, q = 750, 0.4, 0.04, 0.012
    m = price(S, K, T, r, q, sigma, kind)
    assert implied_vol(m, S, K, T, r, q, kind) == pytest.approx(sigma, abs=1e-6)


def test_iv_rejects_arbitrage_quotes():
    S, K, T, r, q = 100, 90, 0.5, 0.05, 0.0
    lo, hi = bounds(S, K, T, r, q, "call")
    assert implied_vol(lo * 0.99, S, K, T, r, q, "call") is None     # below intrinsic value
    assert implied_vol(hi * 1.01, S, K, T, r, q, "call") is None     # above the stock price
    assert implied_vol(0, S, K, T, r, q, "call") is None


def test_vega_positive():
    assert vega(100, 100, 1, 0.05, 0, 0.2) > 0


def test_grid_recovers_flat_surface():
    rows = [dict(strike=k, days=d, iv=0.2) for k in np.linspace(600, 900, 25) for d in (14, 30, 60, 120, 250, 400)]
    K, D, Z = grid(pd.DataFrame(rows), 750)
    assert np.nanmax(np.abs(Z - 0.2)) < 1e-9 and np.isfinite(Z).mean() > 0.8
