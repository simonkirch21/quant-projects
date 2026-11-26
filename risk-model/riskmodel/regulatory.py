"""Mesures réglementaires du risque de marché.

- Bâle 2.5 : VaR 99 % à 10 jours + VaR stressée (calibrée sur une période de
  crise), multipliées par un facteur qui dépend des feux du backtest.
- FRTB (Bâle III) : Expected Shortfall 97,5 %, qui remplace la VaR 99 %.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .var import historical_es, historical_var


def plus_factor(n_exceptions_250: int) -> float:
    """Majoration du multiplicateur de Bâle selon les dépassements sur 250 jours."""
    table = {5: 0.40, 6: 0.50, 7: 0.65, 8: 0.75, 9: 0.85}
    if n_exceptions_250 <= 4:
        return 0.0
    return table.get(n_exceptions_250, 1.0)


def market_risk_capital(var_10d: float, svar_10d: float, n_exceptions_250: int,
                        var_avg60: float | None = None, svar_avg60: float | None = None) -> dict:
    """Capital Bâle 2.5 : max(VaR, m x moyenne 60 j) + max(VaR stressée, m x moyenne 60 j),
    avec m = 3 + majoration."""
    m = 3.0 + plus_factor(n_exceptions_250)
    var_part = max(var_10d, m * (var_avg60 if var_avg60 is not None else var_10d))
    svar_part = max(svar_10d, m * (svar_avg60 if svar_avg60 is not None else svar_10d))
    return {"multiplicateur": m, "VaR": var_part, "VaR stressée": svar_part,
            "capital": var_part + svar_part}


def overlapping_returns(returns: pd.Series, horizon: int) -> pd.Series:
    """Rendements composés sur `horizon` jours, une valeur par jour (fenêtres glissantes)."""
    return (1 + returns).rolling(horizon).apply(np.prod, raw=True).dropna() - 1


def stressed_period(returns: pd.Series, window: int = 250, alpha: float = 0.01) -> tuple:
    """Fenêtre de `window` jours où la VaR historique est la plus élevée."""
    roll = returns.rolling(window).quantile(alpha).mul(-1)
    end = roll.idxmax()
    start = returns.index[returns.index.get_loc(end) - window + 1]
    return start, end


def horizon_comparison(returns: pd.Series, horizon: int = 10, alpha: float = 0.01) -> dict:
    """VaR et ES à 10 jours : règle de la racine du temps contre rendements réels sur 10 jours."""
    r10 = overlapping_returns(returns, horizon)
    root = math.sqrt(horizon)
    return {
        "VaR racine du temps": historical_var(returns, alpha) * root,
        "VaR 10 jours observée": historical_var(r10, alpha),
        "ES racine du temps": historical_es(returns, alpha) * root,
        "ES 10 jours observée": historical_es(r10, alpha),
    }
