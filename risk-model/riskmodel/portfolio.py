"""Risque d'un portefeuille : VaR par la matrice de covariance et contributions."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def portfolio_returns(returns: pd.DataFrame, weights: dict) -> pd.Series:
    """Rendement d'un portefeuille rééquilibré chaque jour aux poids donnés."""
    w = pd.Series(weights)[returns.columns]
    return (returns * w).sum(axis=1).rename("portefeuille")


def risk_contributions(returns: pd.DataFrame, weights: dict, alpha: float = 0.01) -> pd.DataFrame:
    """VaR paramétrique du portefeuille et part de chaque actif.

    sigma_p = sqrt(w' Σ w). Contribution de l'actif i : w_i (Σ w)_i / sigma_p.
    Les contributions s'additionnent exactement à sigma_p (théorème d'Euler),
    donc aussi à la VaR.
    """
    w = pd.Series(weights)[returns.columns].to_numpy()
    cov = returns.cov().to_numpy()
    sigma_p = float(np.sqrt(w @ cov @ w))
    contrib_sigma = w * (cov @ w) / sigma_p
    z = -norm.ppf(alpha)
    return pd.DataFrame(
        {
            "poids": w,
            "volatilité seule": np.sqrt(np.diag(cov)),
            "contribution VaR": contrib_sigma * z,
            "part du risque": contrib_sigma / sigma_p,
        },
        index=returns.columns,
    )
