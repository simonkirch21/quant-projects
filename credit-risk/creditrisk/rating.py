"""Échelle de notation (master scale) et calibration des PD par classe.

Les clients sont rangés en classes selon leur score. La PD d'une classe est
le taux de défaut observé dans cette classe sur l'échantillon d'apprentissage.
C'est ainsi que les banques calibrent : la PD est un taux de défaut moyen
observé, pas directement la sortie du modèle.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import binomtest

GRADES = ["A", "B", "C", "D", "E", "F", "G"]


class MasterScale:
    def __init__(self, quantiles=(0.15, 0.35, 0.55, 0.70, 0.82, 0.92)):
        # Bornes en quantiles de PD : les classes G (pires) sont plus étroites
        self.quantiles = quantiles

    def fit(self, pd_train, y_train) -> "MasterScale":
        cuts = np.quantile(pd_train, self.quantiles)
        self.edges = np.concatenate([[-np.inf], cuts, [np.inf]])
        g = self.grade(pd_train)
        self.grade_pd = pd.Series(np.asarray(y_train)).groupby(g).mean().reindex(GRADES)
        return self

    def grade(self, pd_) -> np.ndarray:
        idx = np.searchsorted(self.edges, np.asarray(pd_), side="right") - 1
        return np.array(GRADES)[np.clip(idx, 0, len(GRADES) - 1)]

    def calibrated_pd(self, pd_) -> np.ndarray:
        return self.grade_pd.loc[self.grade(pd_)].to_numpy()

    def backtest(self, pd_test, y_test, alpha: float = 0.05) -> pd.DataFrame:
        """Pour chaque classe : défauts observés contre PD calibrée (test binomial bilatéral)."""
        g = self.grade(pd_test)
        y = np.asarray(y_test)
        rows = []
        for grade in GRADES:
            m = g == grade
            n, d, p = int(m.sum()), int(y[m].sum()), float(self.grade_pd[grade])
            pv = binomtest(d, n, p).pvalue if n else np.nan
            rows.append({"classe": grade, "clients": n, "PD calibrée": p,
                         "taux observé": d / n if n else np.nan, "p_value": pv,
                         "verdict": "ok" if pv > alpha else "écart"})
        return pd.DataFrame(rows).set_index("classe")

    def global_test(self, pd_test, y_test) -> dict:
        """Test global (Hosmer-Lemeshow par classe) : somme des écarts au carré, khi-deux à 7 degrés."""
        from scipy.stats import chi2
        t = self.backtest(pd_test, y_test)
        exp = t["clients"] * t["PD calibrée"]
        obs = t["clients"] * t["taux observé"]
        stat = float((((obs - exp) ** 2) / (exp * (1 - t["PD calibrée"]))).sum())
        return {"statistique": stat, "p_value": float(chi2.sf(stat, len(t)))}
