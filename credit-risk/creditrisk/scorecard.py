"""Grille de score : régression logistique sur les WoE, convertie en points.

Échelle usuelle : 600 points pour une cote de 50 bons pour 1 mauvais, et
20 points de plus chaque fois que la cote double (PDO, « points to double the odds »).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from .woe import WoEEncoder


class Scorecard:
    def __init__(self, n_bins=6, categorical=("education",), min_iv=0.02,
                 base_score=600, base_odds=50, pdo=20):
        self.encoder = WoEEncoder(n_bins, categorical)
        self.min_iv = min_iv
        self.factor = pdo / math.log(2)
        self.offset = base_score - self.factor * math.log(base_odds)

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "Scorecard":
        self.encoder.fit(X, y)
        iv = self.encoder.information_values()
        self.features = list(iv[iv >= self.min_iv].index)
        W_all = self.encoder.transform(X)
        self.removed = []
        while True:
            self.model = LogisticRegression(C=1e6, max_iter=1_000).fit(W_all[self.features], y)
            coef = self.coefficients()
            # Avec des WoE (élevé = plus sûr), tout coefficient doit être négatif. Un signe
            # positif vient d'une redondance entre variables : on retire la pire et on recommence.
            if (coef < 0).all():
                return self
            worst = coef.idxmax()
            self.removed.append(worst)
            self.features.remove(worst)

    def predict_pd(self, X: pd.DataFrame) -> np.ndarray:
        W = self.encoder.transform(X)[self.features]
        return self.model.predict_proba(W)[:, 1]

    def score(self, X: pd.DataFrame) -> np.ndarray:
        """Score en points : plus il est élevé, plus le client est sûr."""
        p = self.predict_pd(X)
        return self.offset + self.factor * np.log((1 - p) / p)

    def coefficients(self) -> pd.Series:
        return pd.Series(self.model.coef_[0], index=self.features)

    def points_table(self) -> pd.DataFrame:
        """Points attribués à chaque classe de chaque variable (la « grille »)."""
        n = len(self.features)
        b0 = self.model.intercept_[0]
        rows = []
        for f, beta in self.coefficients().items():
            for cls, woe in self.encoder.tables[f]["woe"].items():
                # log-cote(bon) = -(b0 + somme beta x WoE) ; points répartis à parts égales
                pts = self.factor * (-beta * woe - b0 / n) + self.offset / n
                rows.append({"variable": f, "classe": cls, "woe": woe, "points": pts})
        return pd.DataFrame(rows)
