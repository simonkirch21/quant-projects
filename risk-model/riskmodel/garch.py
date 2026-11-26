"""Modèle GARCH(1,1) à innovations de Student, estimé par maximum de vraisemblance.

    sigma²_t = omega + a r²_{t-1} + b sigma²_{t-1}

La volatilité de demain dépend du choc d'aujourd'hui (a) et de la volatilité
d'aujourd'hui (b) : elle monte vite après un krach, puis revient lentement
vers son niveau moyen omega / (1 - a - b). La loi de Student, à queues plus
épaisses que la normale, capte les krachs que la volatilité seule n'explique pas.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.signal import lfilter
from scipy.special import gammaln
from scipy.stats import t as student_t


def garch_variance(r: np.ndarray, omega: float, a: float, b: float) -> np.ndarray:
    """sigma²_t pour chaque t, calculée avec les rendements jusqu'à t - 1.

    Récurrence linéaire calculée par un filtre (scipy.signal.lfilter) :
    var[t + 1] = omega + a r[t]² + b var[t], avec var[0] = variance de l'échantillon.
    """
    r = np.asarray(r, dtype=float)
    v0 = r.var()
    x = omega + a * r**2
    rest = lfilter([1.0], [1.0, -b], x, zi=[b * v0])[0]
    return np.concatenate([[v0], rest])  # var[t] = prévision pour le jour t ; var[-1] = demain


def _neg_loglik(params, r):
    omega, a, b, nu = params
    if omega <= 0 or a < 0 or b < 0 or a + b >= 0.9999 or nu <= 2.05:
        return 1e10
    s2 = garch_variance(r, omega, a, b)[:-1]
    z2 = r**2 / s2
    ll = (gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * math.log(math.pi * (nu - 2))
          - 0.5 * np.log(s2) - (nu + 1) / 2 * np.log1p(z2 / (nu - 2)))
    return -ll.sum()


def fit_garch_t(returns) -> dict:
    r = np.asarray(returns, dtype=float)
    r = r - r.mean()
    v = r.var()
    best = None
    for a0, b0 in ((0.05, 0.90), (0.10, 0.85), (0.03, 0.95)):
        x0 = [v * (1 - a0 - b0), a0, b0, 8.0]
        res = minimize(_neg_loglik, x0, args=(r,), method="Nelder-Mead",
                       options={"maxiter": 4000, "xatol": 1e-10, "fatol": 1e-6})
        if best is None or res.fun < best.fun:
            best = res
    omega, a, b, nu = best.x
    return {"omega": omega, "a": a, "b": b, "nu": nu, "persistance": a + b,
            "vol long terme annuelle": math.sqrt(omega / (1 - a - b) * 252), "loglik": -best.fun}


def student_quantile(alpha: float, nu: float) -> float:
    """Quantile d'une loi de Student ramenée à une variance de 1."""
    return student_t.ppf(alpha, nu) * math.sqrt((nu - 2) / nu)


def garch_var_forecast(returns: pd.Series, alpha: float = 0.01, first_year: int | None = None,
                       min_obs: int = 500) -> pd.Series:
    """Prévision de VaR à 1 jour, sans regarder le futur.

    Les paramètres sont réestimés chaque 1er janvier sur tout l'historique
    disponible jusqu'au 31 décembre précédent, puis appliqués pendant l'année.
    """
    out = pd.Series(np.nan, index=returns.index, name="garch_t")
    years = sorted(set(returns.index.year))
    for year in years:
        past = returns.loc[: f"{year - 1}-12-31"]
        if len(past) < min_obs or (first_year and year < first_year):
            continue
        p = fit_garch_t(past.to_numpy())
        upto = returns.loc[: f"{year}-12-31"]
        r = (upto - past.mean()).to_numpy()
        s2 = garch_variance(r, p["omega"], p["a"], p["b"])[:-1]
        sigma = pd.Series(np.sqrt(s2), index=upto.index).loc[str(year)]
        out.loc[sigma.index] = -(past.mean() + sigma * student_quantile(alpha, p["nu"]))
    return out
