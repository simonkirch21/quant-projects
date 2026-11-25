"""Rendements journaliers, lus dans les prix déjà téléchargés par le backtester."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "backtester" / "data"


def load_returns(tickers: list[str]) -> pd.DataFrame:
    """Tableau des rendements journaliers (une colonne par actif)."""
    prices = pd.concat(
        {t: pd.read_csv(DATA_DIR / f"{t}.csv", index_col=0, parse_dates=True).iloc[:, 0]
         for t in tickers},
        axis=1,
    ).dropna()
    return prices.pct_change().dropna()
