"""Black-Scholes : prix fermé, grecques analytiques et volatilité implicite.

Option européenne sur un sous-jacent sans dividende, ou avec un rendement
de dividende continu q (modèle de Merton).

Notations :
    S     prix spot du sous-jacent
    K     prix d'exercice (strike)
    T     maturité en années
    r     taux sans risque continu
    sigma volatilité annuelle
    q     rendement de dividende continu (0 par défaut)
"""

from __future__ import annotations

import math

from scipy.optimize import brentq
from scipy.stats import norm


def _check_kind(kind: str) -> str:
    kind = kind.lower()
    if kind not in ("call", "put"):
        raise ValueError("kind doit valoir 'call' ou 'put'")
    return kind


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0):
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        raise ValueError("S, K, T et sigma doivent être strictement positifs")
    vol_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / vol_sqrt_t
    return d1, d1 - vol_sqrt_t


def bs_price(S, K, T, r, sigma, kind="call", q=0.0) -> float:
    """Prix Black-Scholes d'un call ou d'un put européen."""
    kind = _check_kind(kind)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    df_r, df_q = math.exp(-r * T), math.exp(-q * T)
    if kind == "call":
        return S * df_q * norm.cdf(d1) - K * df_r * norm.cdf(d2)
    return K * df_r * norm.cdf(-d2) - S * df_q * norm.cdf(-d1)


def bs_greeks(S, K, T, r, sigma, kind="call", q=0.0) -> dict:
    """Grecques analytiques.

    Conventions :
        delta : dV/dS
        gamma : d²V/dS²
        vega  : dV/dsigma, pour une variation de 1 (100 points de vol)
        theta : dV/dt, par an (= -dV/dT)
        rho   : dV/dr, pour une variation de 1 (100 points de taux)
    """
    kind = _check_kind(kind)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    df_r, df_q = math.exp(-r * T), math.exp(-q * T)
    pdf_d1 = norm.pdf(d1)
    sqrt_t = math.sqrt(T)

    gamma = df_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * df_q * pdf_d1 * sqrt_t
    common_theta = -S * df_q * pdf_d1 * sigma / (2 * sqrt_t)

    if kind == "call":
        delta = df_q * norm.cdf(d1)
        theta = common_theta - r * K * df_r * norm.cdf(d2) + q * S * df_q * norm.cdf(d1)
        rho = K * T * df_r * norm.cdf(d2)
    else:
        delta = -df_q * norm.cdf(-d1)
        theta = common_theta + r * K * df_r * norm.cdf(-d2) - q * S * df_q * norm.cdf(-d1)
        rho = -K * T * df_r * norm.cdf(-d2)

    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def implied_vol(price, S, K, T, r, kind="call", q=0.0, lo=1e-6, hi=5.0) -> float:
    """Volatilité implicite par la méthode de Brent.

    Lève ValueError si le prix est hors des bornes d'arbitrage.
    """
    kind = _check_kind(kind)
    df_r, df_q = math.exp(-r * T), math.exp(-q * T)
    if kind == "call":
        lower, upper = max(S * df_q - K * df_r, 0.0), S * df_q
    else:
        lower, upper = max(K * df_r - S * df_q, 0.0), K * df_r
    if not lower < price < upper:
        raise ValueError(
            f"prix {price:.6f} hors des bornes d'arbitrage ]{lower:.6f} ; {upper:.6f}["
        )
    return brentq(lambda s: bs_price(S, K, T, r, s, kind, q) - price, lo, hi, xtol=1e-12)
