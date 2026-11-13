"""Black-Scholes-Merton pricing and implied volatility (Hull, *Options, Futures, and Other Derivatives*, ch. 15 and 17).

A stock or index that pays a continuous dividend yield q:

    d1 = [ln(S/K) + (r - q + σ²/2)·T] / (σ·√T)
    d2 = d1 - σ·√T
    call = S·e^(-qT)·N(d1) - K·e^(-rT)·N(d2)
    put  = K·e^(-rT)·N(-d2) - S·e^(-qT)·N(-d1)

Implied volatility is the σ that makes the model price equal the market price. There is no closed form, but the
price rises steadily with σ (vega > 0), so there is exactly one root, and Brent's method (scipy.optimize.brentq)
finds it reliably inside a bracket.
"""
from __future__ import annotations

import math

from scipy.optimize import brentq
from scipy.stats import norm

SIGMA_LO, SIGMA_HI = 1e-4, 5.0   # 0.01% to 500% vol: the search bracket


def d1_d2(S: float, K: float, T: float, r: float, q: float, sigma: float) -> tuple[float, float]:
    v = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / v
    return d1, d1 - v


def price(S: float, K: float, T: float, r: float, q: float, sigma: float, kind: str) -> float:
    d1, d2 = d1_d2(S, K, T, r, q, sigma)
    if kind == "call":
        return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)


def vega(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
    d1, _ = d1_d2(S, K, T, r, q, sigma)
    return S * math.exp(-q * T) * norm.pdf(d1) * math.sqrt(T)


def bounds(S: float, K: float, T: float, r: float, q: float, kind: str) -> tuple[float, float]:
    """No-arbitrage range of an option price. A quote outside it has no implied volatility."""
    fwd_s, pv_k = S * math.exp(-q * T), K * math.exp(-r * T)
    if kind == "call":
        return max(fwd_s - pv_k, 0.0), fwd_s
    return max(pv_k - fwd_s, 0.0), pv_k


def implied_vol(market: float, S: float, K: float, T: float, r: float, q: float, kind: str) -> float | None:
    """σ such that price(σ) = market, or None when the quote breaks the no-arbitrage bounds."""
    if T <= 0 or market <= 0:
        return None
    lo, hi = bounds(S, K, T, r, q, kind)
    if not (lo < market < hi):
        return None
    f = lambda s: price(S, K, T, r, q, s, kind) - market
    try:
        if f(SIGMA_LO) > 0 or f(SIGMA_HI) < 0:
            return None
        return brentq(f, SIGMA_LO, SIGMA_HI, xtol=1e-8, maxiter=200)
    except ValueError:
        return None
