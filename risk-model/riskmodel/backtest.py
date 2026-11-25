"""Backtest d'une VaR : la prévision a-t-elle été dépassée aussi souvent qu'annoncé ?"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import chi2


def exceptions(returns: pd.Series, var_forecast: pd.Series) -> pd.Series:
    """True les jours où la perte a dépassé la VaR prévue."""
    df = pd.concat({"r": returns, "var": var_forecast}, axis=1).dropna()
    return (-df["r"] > df["var"]).rename("exception")


def _xlogy(x, y):
    return 0.0 if x == 0 else x * math.log(y)


def kupiec_pof(n_obs: int, n_exc: int, alpha: float = 0.01) -> dict:
    """Test de Kupiec (proportion of failures).

    H0 : la vraie fréquence des dépassements vaut alpha.
    Statistique LR ~ chi2(1) sous H0. p-value < 5 % -> on rejette le modèle.
    """
    x, n = n_exc, n_obs
    p_hat = x / n
    ll_h0 = _xlogy(n - x, 1 - alpha) + _xlogy(x, alpha)
    ll_h1 = _xlogy(n - x, 1 - p_hat) + _xlogy(x, p_hat)
    lr = -2 * (ll_h0 - ll_h1)
    return {"exceptions": x, "attendues": alpha * n, "taux": p_hat,
            "LR": lr, "p_value": float(chi2.sf(lr, 1))}


def christoffersen_independence(exc: pd.Series) -> dict:
    """Test d'indépendance de Christoffersen.

    Un bon modèle a des dépassements dispersés. S'ils arrivent en grappes
    (un dépassement rend le suivant plus probable), le modèle réagit trop
    lentement aux changements de volatilité.
    """
    e = np.asarray(exc, dtype=int)
    prev, curr = e[:-1], e[1:]
    n00 = int(((prev == 0) & (curr == 0)).sum())
    n01 = int(((prev == 0) & (curr == 1)).sum())
    n10 = int(((prev == 1) & (curr == 0)).sum())
    n11 = int(((prev == 1) & (curr == 1)).sum())
    pi0 = n01 / (n00 + n01) if n00 + n01 else 0.0
    pi1 = n11 / (n10 + n11) if n10 + n11 else 0.0
    pi = (n01 + n11) / (n00 + n01 + n10 + n11)
    ll_h0 = _xlogy(n00 + n10, 1 - pi) + _xlogy(n01 + n11, pi)
    ll_h1 = (_xlogy(n00, 1 - pi0) + _xlogy(n01, pi0)
             + _xlogy(n10, 1 - pi1) + _xlogy(n11, pi1))
    lr = -2 * (ll_h0 - ll_h1)
    return {"P(exc | veille sans)": pi0, "P(exc | veille avec)": pi1,
            "LR": lr, "p_value": float(chi2.sf(lr, 1))}


def basel_zone(n_exc_250: int) -> str:
    """Feux tricolores de Bâle : VaR 99 %, 250 derniers jours."""
    if n_exc_250 <= 4:
        return "vert"
    if n_exc_250 <= 9:
        return "orange"
    return "rouge"
