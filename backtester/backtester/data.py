"""Chargement des prix historiques.

Les prix viennent de Yahoo Finance (bibliothèque yfinance). Ils sont
« ajustés » : corrigés des dividendes et des divisions d'actions (splits),
pour que la variation d'un jour à l'autre reflète le vrai gain d'un
investisseur.

Le premier téléchargement est enregistré dans data/<TICKER>.csv. Ensuite,
on relit ce fichier : les résultats sont reproductibles et on n'a plus
besoin d'internet.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def load_prices(ticker: str, start: str = "2005-01-01", end: str = "2025-01-01") -> pd.Series:
    """Série des prix de clôture ajustés, indexée par date."""
    path = DATA_DIR / f"{ticker}.csv"
    if path.exists():
        prices = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
    else:
        import yfinance as yf

        raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if raw.empty:
            raise RuntimeError(f"aucune donnée téléchargée pour {ticker}")
        prices = raw["Close"].squeeze()
        DATA_DIR.mkdir(exist_ok=True)
        prices.rename("close").to_csv(path)
    prices.name = ticker
    return prices.loc[start:end].dropna()


def daily_returns(prices: pd.Series) -> pd.Series:
    """Rendement de chaque jour : prix du jour / prix de la veille - 1."""
    return prices.pct_change().dropna()
