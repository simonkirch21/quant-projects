"""Perte attendue et capital réglementaire (approche IRB de Bâle).

Perte attendue (EL, provisionnée) : EL = PD x LGD x EAD.
Perte inattendue (couverte par les fonds propres) : formule de Vasicek,
quantile 99,9 % d'un modèle à un facteur (ASRF).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

R_QRRE = 0.04          # corrélation fixée par Bâle pour les crédits renouvelables aux particuliers
PD_FLOOR = 0.0005      # plancher de PD (0,05 %)


def expected_loss(pd_, lgd, ead):
    return np.asarray(pd_) * lgd * np.asarray(ead)


def vasicek_conditional_pd(pd_, rho, q: float = 0.999):
    """PD dans le scénario économique défavorable de probabilité 1 - q."""
    pd_ = np.clip(np.asarray(pd_, dtype=float), PD_FLOOR, 1 - 1e-12)
    return norm.cdf((norm.ppf(pd_) + np.sqrt(rho) * norm.ppf(q)) / np.sqrt(1 - rho))


def irb_capital_k(pd_, lgd, rho: float = R_QRRE):
    """Capital par euro d'exposition : K = LGD x [PD conditionnelle à 99,9 % - PD]
    (pas d'ajustement de maturité pour la clientèle de détail)."""
    pd_ = np.clip(np.asarray(pd_, dtype=float), PD_FLOOR, 1.0)
    return lgd * (vasicek_conditional_pd(pd_, rho) - pd_)


def risk_weighted_assets(pd_, lgd, ead, rho: float = R_QRRE):
    """RWA = 12,5 x K x EAD (le capital minimum vaut 8 % des RWA, soit K x EAD)."""
    return 12.5 * irb_capital_k(pd_, lgd, rho) * np.asarray(ead)


def simulate_portfolio_losses(pd_, lgd, ead, rho, n_sims: int = 20_000, seed: int = 0,
                              chunk: int = 500) -> np.ndarray:
    """Pertes du portefeuille par Monte Carlo (modèle de Vasicek à un facteur).

    Emprunteur i en défaut si  sqrt(rho) Z + sqrt(1 - rho) e_i < N^-1(PD_i),
    avec Z le facteur économique commun à tous et e_i le risque propre.
    """
    rng = np.random.default_rng(seed)
    pd_ = np.clip(np.asarray(pd_, dtype=float), PD_FLOOR, 1 - 1e-12)
    thresholds = norm.ppf(pd_)
    exposure = lgd * np.asarray(ead, dtype=float)
    losses = np.empty(n_sims)
    for start in range(0, n_sims, chunk):
        m = min(chunk, n_sims - start)
        z = rng.standard_normal((m, 1))
        eps = rng.standard_normal((m, len(pd_)))
        default = np.sqrt(rho) * z + np.sqrt(1 - rho) * eps < thresholds
        losses[start:start + m] = default @ exposure
    return losses
