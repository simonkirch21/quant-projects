"""Stratégies : à partir des prix, produisent un signal pour chaque jour.

Un signal vaut 1 (« je veux être investi ») ou 0 (« je veux être en cash »).
Il est calculé avec le prix de clôture du jour : on ne le connaît donc
qu'en fin de journée.
"""

from __future__ import annotations

import pandas as pd


def buy_and_hold(prices: pd.Series) -> pd.Series:
    """Toujours investi : la référence à battre."""
    return pd.Series(1.0, index=prices.index)


def sma_trend(prices: pd.Series, window: int = 200) -> pd.Series:
    """Investi si le prix est au-dessus de sa moyenne des `window` derniers jours.

    Tant qu'il n'y a pas assez d'historique pour calculer la moyenne, on reste
    en cash (0).
    """
    sma = prices.rolling(window).mean()
    return (prices > sma).astype(float).where(sma.notna(), 0.0)
