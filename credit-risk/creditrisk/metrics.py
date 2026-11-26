"""Mesures de performance d'un modèle de score, utilisées en validation bancaire."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2
from sklearn.metrics import roc_auc_score


def auc(y, pd_) -> float:
    """Probabilité qu'un mauvais client tiré au hasard ait une PD plus élevée qu'un bon."""
    return float(roc_auc_score(y, pd_))


def gini(y, pd_) -> float:
    """Gini = 2 AUC - 1 : 0 = hasard, 1 = classement parfait."""
    return 2 * auc(y, pd_) - 1


def ks(y, pd_) -> float:
    """Kolmogorov-Smirnov : écart maximal entre les répartitions des bons et des mauvais."""
    y, s = np.asarray(y), np.asarray(pd_)
    order = np.argsort(-s)
    y = y[order]
    cum_bad = np.cumsum(y) / y.sum()
    cum_good = np.cumsum(1 - y) / (1 - y).sum()
    return float(np.max(np.abs(cum_bad - cum_good)))


def calibration_table(y, pd_, n_groups: int = 10) -> pd.DataFrame:
    df = pd.DataFrame({"y": np.asarray(y), "pd": np.asarray(pd_)})
    df["groupe"] = pd.qcut(df["pd"].rank(method="first"), n_groups, labels=False) + 1
    g = df.groupby("groupe").agg(n=("y", "size"), pd_moyenne=("pd", "mean"), taux_observe=("y", "mean"))
    return g


def hosmer_lemeshow(y, pd_, n_groups: int = 10, in_sample: bool = False) -> dict:
    """Test d'adéquation : les PD prévues correspondent-elles aux taux observés ?

    Degrés de liberté : n_groups - 2 si les PD ont été estimées sur ces mêmes
    données (in_sample=True), n_groups pour des PD jugées sur un autre
    échantillon (validation hors échantillon, le cas usuel en banque).
    """
    t = calibration_table(y, pd_, n_groups)
    exp_bad = t["n"] * t["pd_moyenne"]
    obs_bad = t["n"] * t["taux_observe"]
    stat = (((obs_bad - exp_bad) ** 2) / (exp_bad * (1 - t["pd_moyenne"]))).sum()
    dof = n_groups - 2 if in_sample else n_groups
    return {"statistique": float(stat), "p_value": float(chi2.sf(stat, dof))}


def brier(y, pd_) -> float:
    return float(np.mean((np.asarray(pd_) - np.asarray(y)) ** 2))


def psi(expected, actual, n_bins: int = 10) -> float:
    """Population Stability Index : la population a-t-elle changé entre deux échantillons ?
    < 0,1 stable ; 0,1-0,25 à surveiller ; > 0,25 changement important."""
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, n_bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    e = np.histogram(expected, edges)[0] / len(expected)
    a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, 1e-6, None), np.clip(a, 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))
