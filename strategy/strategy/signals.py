"""Stratégie multi-actifs : suivi de tendance + ciblage de volatilité.

Pour chaque actif (actions, obligations, or), chaque soir :
  1. Tendance : investi si le prix est au-dessus de sa moyenne mobile de
     `window` jours, sinon en cash.
  2. Taille : position = volatilité cible / volatilité récente (60 jours),
     plafonnée à 1 (pas d'effet de levier). Quand un actif devient agité,
     on en détient moins.
  3. Chaque actif reçoit le même budget (1/3).

Le moteur du backtester décale ensuite ce signal d'un jour.
"""

from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS = 252


def trend(prices: pd.Series, window: int) -> pd.Series:
    sma = prices.rolling(window).mean()
    return (prices > sma).astype(float).where(sma.notna(), 0.0)


def vol_scale(prices: pd.Series, target_vol: float = 0.10, lookback: int = 60) -> pd.Series:
    vol = prices.pct_change().rolling(lookback).std() * math.sqrt(TRADING_DAYS)
    return (target_vol / vol).clip(upper=1.0).fillna(0.0)


def target_weights(prices: pd.DataFrame, window: int, target_vol: float = 0.10,
                   use_trend: bool = True, use_vol: bool = True) -> pd.DataFrame:
    """Poids souhaités (signal) pour chaque actif et chaque jour."""
    budget = 1.0 / prices.shape[1]
    out = {}
    for col in prices:
        w = pd.Series(budget, index=prices.index)
        if use_trend:
            w = w * trend(prices[col], window)
        if use_vol:
            w = w * vol_scale(prices[col], target_vol)
        out[col] = w
    return pd.DataFrame(out)
