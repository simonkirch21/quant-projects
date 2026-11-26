"""Découpage en classes et Weight of Evidence (WoE), la méthode standard des
grilles de score bancaires.

Pour chaque classe d'une variable :
    WoE = ln( part des bons clients dans la classe / part des mauvais )
WoE > 0 : classe plus sûre que la moyenne ; WoE < 0 : plus risquée.

Information Value : IV = somme (part bons - part mauvais) x WoE.
Repères usuels : < 0,02 inutile ; 0,02-0,1 faible ; 0,1-0,3 moyen ; > 0,3 fort.

Les classes et les WoE sont calculés sur l'échantillon d'apprentissage
seulement, puis appliqués tels quels à l'échantillon de test.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 0.5   # lissage : évite ln(0) dans une classe sans aucun défaut


def quantile_edges(x: pd.Series, n_bins: int = 6) -> np.ndarray:
    edges = np.unique(np.quantile(x, np.linspace(0, 1, n_bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    return edges


def woe_table(bins: pd.Series, y: pd.Series) -> pd.DataFrame:
    t = pd.crosstab(bins, y).reindex(columns=[0, 1], fill_value=0)
    t.columns = ["bons", "mauvais"]
    good = (t["bons"] + EPS) / (t["bons"].sum() + EPS * len(t))
    bad = (t["mauvais"] + EPS) / (t["mauvais"].sum() + EPS * len(t))
    t["taux_defaut"] = t["mauvais"] / (t["bons"] + t["mauvais"])
    t["woe"] = np.log(good / bad)
    t["iv"] = (good - bad) * t["woe"]
    return t


class WoEEncoder:
    """Apprend les classes et les WoE sur l'apprentissage, transforme n'importe quel échantillon."""

    def __init__(self, n_bins: int = 6, categorical: tuple = ()):
        self.n_bins = n_bins
        self.categorical = set(categorical)
        self.edges, self.tables = {}, {}

    def _bin(self, col: str, x: pd.Series) -> pd.Series:
        if col in self.categorical:
            return x.astype(str)
        return pd.cut(x, self.edges[col], include_lowest=True).astype(str)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "WoEEncoder":
        for col in X:
            if col not in self.categorical:
                self.edges[col] = quantile_edges(X[col], self.n_bins)
            self.tables[col] = woe_table(self._bin(col, X[col]), y)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        out = {}
        for col, table in self.tables.items():
            out[col] = self._bin(col, X[col]).map(table["woe"]).fillna(0.0)   # classe inconnue : neutre
        return pd.DataFrame(out, index=X.index)

    def information_values(self) -> pd.Series:
        return pd.Series({c: t["iv"].sum() for c, t in self.tables.items()}).sort_values(ascending=False)
