"""Outils statistiques pour juger si un Sharpe est réel ou dû à la chance."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

EULER_GAMMA = 0.5772156649015329


def probabilistic_sharpe_ratio(returns: pd.Series, sr_benchmark: float = 0.0) -> float:
    """Probabilité que le vrai Sharpe dépasse sr_benchmark (Bailey et López de Prado, 2012).

    Tient compte de la durée de l'historique, de l'asymétrie et des queues
    épaisses. Sharpe exprimés par jour (non annualisés).
    """
    r = np.asarray(returns)
    sr = r.mean() / r.std(ddof=1)
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    denom = math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr**2)
    return float(norm.cdf((sr - sr_benchmark) * math.sqrt(len(r) - 1) / denom))


def expected_max_sharpe(sharpe_variance: float, n_trials: int) -> float:
    """Sharpe maximal attendu PAR PUR HASARD parmi n_trials stratégies sans talent."""
    if n_trials < 2:
        return 0.0
    return math.sqrt(sharpe_variance) * (
        (1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials)
        + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * math.e))
    )


def deflated_sharpe_ratio(returns: pd.Series, trial_sharpes: list[float]) -> float:
    """Deflated Sharpe Ratio (Bailey et López de Prado, 2014).

    Probabilité que le Sharpe soit réel, une fois corrigé du nombre d'essais :
    on le compare au meilleur Sharpe qu'on aurait obtenu par chance en testant
    autant de variantes. trial_sharpes : Sharpe journaliers de toutes les
    variantes essayées.
    """
    sr0 = expected_max_sharpe(float(np.var(trial_sharpes, ddof=1)), len(trial_sharpes))
    return probabilistic_sharpe_ratio(returns, sr0)


def block_bootstrap_sharpe(returns: pd.Series, n_boot: int = 2_000, block: int = 20,
                           seed: int = 0) -> np.ndarray:
    """Sharpe annualisés obtenus en rééchantillonnant l'historique par blocs
    de `block` jours (les blocs gardent les grappes de volatilité)."""
    r = np.asarray(returns)
    n = len(r)
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / block)
    out = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        sample = np.concatenate([r[s:s + block] for s in starts])[:n]
        out[b] = sample.mean() / sample.std(ddof=1) * math.sqrt(252)
    return out


def block_bootstrap_sharpe_diff(a: pd.Series, b: pd.Series, n_boot: int = 2_000,
                                block: int = 20, seed: int = 0) -> np.ndarray:
    """Différence de Sharpe annualisés (a - b), avec les MÊMES jours tirés pour
    les deux stratégies à chaque rééchantillonnage (comparaison appariée)."""
    df = pd.concat([a, b], axis=1).dropna().to_numpy()
    n = len(df)
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / block)
    out = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, n - block + 1, n_blocks)
        s = np.concatenate([df[k:k + block] for k in starts])[:n]
        sr = s.mean(axis=0) / s.std(axis=0, ddof=1) * math.sqrt(252)
        out[i] = sr[0] - sr[1]
    return out
