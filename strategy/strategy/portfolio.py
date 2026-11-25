"""Backtest multi-actifs, en réutilisant le moteur du projet 2 actif par actif."""

from __future__ import annotations

import pandas as pd

from backtester.engine import run_backtest


def run_portfolio(prices: pd.DataFrame, weights: pd.DataFrame, cost: float = 0.001) -> pd.Series:
    """Rendement journalier du portefeuille, frais déduits.

    Chaque actif est passé dans run_backtest avec son poids comme signal
    (décalage d'un jour et frais compris) ; les rendements s'additionnent.
    """
    total = sum(
        run_backtest(prices[col], weights[col], cost=cost)["strategy_return"]
        for col in prices
    )
    return total.rename("portefeuille")


def equity(returns: pd.Series) -> pd.Series:
    return (1 + returns).cumprod()
