"""Validation walk-forward : choisir les paramètres sans jamais regarder l'avenir.

Chaque 1er janvier, on teste tous les paramètres candidats sur les
`train_years` années précédentes, on garde le meilleur (Sharpe), et on
l'applique tel quel à l'année qui commence. On recommence l'année suivante.
La performance finale n'est faite QUE d'années que le choix n'avait pas vues.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

from backtester.metrics import sharpe_ratio


def walk_forward(
    returns_by_param: dict[int, pd.Series],
    first_test_year: int,
    last_test_year: int,
    train_years: int = 5,
    score: Callable[[pd.Series], float] = sharpe_ratio,
) -> tuple[pd.Series, pd.Series]:
    """returns_by_param : rendements journaliers de la stratégie pour chaque
    paramètre (déjà calculés sans biais d'anticipation).

    Renvoie (rendements hors échantillon mis bout à bout, paramètre choisi par année).
    """
    oos, chosen = [], {}
    for year in range(first_test_year, last_test_year + 1):
        train = slice(f"{year - train_years}-01-01", f"{year - 1}-12-31")
        best = max(returns_by_param, key=lambda p: score(returns_by_param[p].loc[train]))
        chosen[year] = best
        oos.append(returns_by_param[best].loc[str(year)])
    return pd.concat(oos), pd.Series(chosen, name="paramètre choisi")
