"""Théorie des valeurs extrêmes : méthode des excès au-delà d'un seuil (POT).

Au-delà d'un seuil élevé u, les excès de perte suivent approximativement une
loi de Pareto généralisée (GPD) de paramètres xi (forme) et beta (échelle),
quelle que soit la loi d'origine (théorème de Pickands-Balkema-de Haan).
xi > 0 signale des queues épaisses. On peut alors estimer des quantiles bien
plus extrêmes que ce que permettent les données seules (99,9 %…).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import genpareto


def fit_pot(losses, threshold_quantile: float = 0.95) -> dict:
    x = np.asarray(losses, dtype=float)
    u = float(np.quantile(x, threshold_quantile))
    excess = x[x > u] - u
    xi, _, beta = genpareto.fit(excess, floc=0)
    return {"u": u, "xi": float(xi), "beta": float(beta), "n": len(x), "n_u": len(excess)}


def evt_var(fit: dict, level: float) -> float:
    """VaR au niveau `level` (ex. 0,999), en perte positive."""
    u, xi, beta, n, n_u = fit["u"], fit["xi"], fit["beta"], fit["n"], fit["n_u"]
    tail = n / n_u * (1 - level)
    if abs(xi) < 1e-9:
        return u - beta * np.log(tail)
    return u + beta / xi * (tail ** (-xi) - 1)


def evt_es(fit: dict, level: float) -> float:
    """Expected Shortfall au niveau `level` (défini si xi < 1)."""
    var = evt_var(fit, level)
    xi, beta, u = fit["xi"], fit["beta"], fit["u"]
    return var / (1 - xi) + (beta - xi * u) / (1 - xi)
