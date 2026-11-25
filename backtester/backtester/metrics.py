"""Mesures de performance et de risque d'un backtest."""

from __future__ import annotations

import math

import pandas as pd

TRADING_DAYS = 252  # nombre moyen de jours de bourse par an


def cagr(equity: pd.Series) -> float:
    """Rendement annuel moyen composé (Compound Annual Growth Rate).

    Le taux constant qui, appliqué chaque année, mène de la richesse de
    départ à la richesse finale.
    """
    years = (len(equity) - 1) / TRADING_DAYS
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1


def annual_volatility(returns: pd.Series) -> float:
    """Écart-type des rendements journaliers, ramené à l'année (× racine de 252)."""
    return returns.std(ddof=1) * math.sqrt(TRADING_DAYS)


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.0) -> float:
    """Rendement en excès du taux sans risque, par unité de volatilité (annualisé)."""
    excess = returns - risk_free / TRADING_DAYS
    vol = excess.std(ddof=1)
    return 0.0 if vol == 0 else excess.mean() / vol * math.sqrt(TRADING_DAYS)


def drawdown(equity: pd.Series) -> pd.Series:
    """Chute depuis le plus haut historique, chaque jour (0 = sur un sommet)."""
    return equity / equity.cummax() - 1


def max_drawdown(equity: pd.Series) -> float:
    """Pire chute d'un sommet à un creux (nombre négatif)."""
    return float(drawdown(equity).min())


def summary(bt: pd.DataFrame) -> dict:
    """Tableau de bord d'un backtest produit par run_backtest."""
    ret, eq = bt["strategy_return"], bt["equity"]
    return {
        "richesse finale": eq.iloc[-1],
        "rendement annuel": cagr(eq),
        "volatilité": annual_volatility(ret),
        "sharpe": sharpe_ratio(ret),
        "pire chute": max_drawdown(eq),
        "temps investi": bt["position"].mean(),
        "transactions": int(bt["turnover"].sum()),
    }
