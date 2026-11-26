"""Tests de résistance (stress tests).

Trois approches complémentaires :
  - historique : rejouer une crise passée sur le portefeuille d'aujourd'hui ;
  - hypothétique : appliquer des chocs imaginés (« actions -30 % ») ;
  - inversée (reverse stress test) : partir d'une perte inacceptable et
    chercher le scénario le plus plausible qui la provoque.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm

HISTORICAL_SCENARIOS = {
    "Faillite de Lehman (12/09/2008 → 09/03/2009)": ("2008-09-12", "2009-03-09"),
    "Taper tantrum (21/05/2013 → 24/06/2013)": ("2013-05-21", "2013-06-24"),
    "Krach Covid (19/02/2020 → 23/03/2020)": ("2020-02-19", "2020-03-23"),
    "Hausse des taux (31/12/2021 → 14/10/2022)": ("2021-12-31", "2022-10-14"),
}

# Chocs instantanés par actif. Pour TLT (obligations d'État américaines à
# plus de 20 ans, duration d'environ 17), +2 points de taux donnent environ
# -17 x 2 = -34 %.
HYPOTHETICAL_SCENARIOS = {
    "Krach actions, fuite vers la qualité": {"SPY": -0.30, "TLT": 0.08, "GLD": 0.05},
    "Taux longs +2 points": {"SPY": -0.10, "TLT": -0.34, "GLD": -0.05},
    "Stagflation (actions et obligations chutent)": {"SPY": -0.25, "TLT": -0.20, "GLD": 0.10},
    "Krach de l'or": {"SPY": 0.0, "TLT": 0.0, "GLD": -0.30},
}


def scenario_returns(returns: pd.DataFrame, start: str, end: str) -> pd.Series:
    """Rendement cumulé de chaque actif entre deux clôtures (start exclu)."""
    window = returns.loc[start:end].iloc[1:]
    return (1 + window).prod() - 1


def portfolio_pnl(weights: dict, shocks) -> float:
    """Variation de valeur d'un portefeuille non rééquilibré pendant le choc."""
    return float(sum(w * shocks[k] for k, w in weights.items()))


def historical_stress(returns: pd.DataFrame, weights: dict, scenarios=None) -> pd.DataFrame:
    rows = {}
    for name, (start, end) in (scenarios or HISTORICAL_SCENARIOS).items():
        shocks = scenario_returns(returns, start, end)
        rows[name] = {**shocks.to_dict(), "portefeuille": portfolio_pnl(weights, shocks)}
    return pd.DataFrame(rows).T


def hypothetical_stress(weights: dict, scenarios=None) -> pd.DataFrame:
    rows = {name: {**s, "portefeuille": portfolio_pnl(weights, s)}
            for name, s in (scenarios or HYPOTHETICAL_SCENARIOS).items()}
    return pd.DataFrame(rows).T


def reverse_stress(cov: pd.DataFrame, weights: dict, loss: float) -> dict:
    """Scénario le plus plausible menant à une perte donnée (rendements normaux).

    Parmi tous les chocs x tels que w'x = -loss, celui qui minimise la distance
    de Mahalanobis x' Σ^-1 x est x* = -loss Σw / (w'Σw). Sa distance vaut
    d = loss / σ_p : plus d est grand, moins le scénario est plausible.
    """
    w = pd.Series(weights)[cov.columns].to_numpy()
    sigma = cov.to_numpy()
    var_p = float(w @ sigma @ w)
    shock = -loss * (sigma @ w) / var_p
    d = loss / np.sqrt(var_p)
    return {
        "chocs": pd.Series(shock, index=cov.columns),
        "écarts-types": d,
        "probabilité (loi normale)": float(norm.sf(d)),
    }
