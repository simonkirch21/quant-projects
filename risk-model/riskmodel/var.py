"""Value at Risk (VaR) et Expected Shortfall (ES).

Convention : la VaR et l'ES sont des PERTES, donc des nombres positifs.
VaR 99 % = 2 % signifie : « 99 jours sur 100, on ne perd pas plus de 2 % ».
ES 99 % = perte moyenne les jours où l'on dépasse la VaR (le 1 % des pires jours).

alpha est la probabilité de queue : 0.01 pour un niveau de confiance de 99 %.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm


# --- Méthode historique : on lit directement les pires jours du passé -------

def historical_var(returns, alpha: float = 0.01) -> float:
    return float(-np.quantile(np.asarray(returns), alpha))


def historical_es(returns, alpha: float = 0.01) -> float:
    r = np.asarray(returns)
    tail = r[r <= np.quantile(r, alpha)]
    return float(-tail.mean())


# --- Méthode paramétrique : on suppose des rendements de loi normale --------

def normal_var(mu: float, sigma: float, alpha: float = 0.01) -> float:
    return -(mu + sigma * norm.ppf(alpha))


def normal_es(mu: float, sigma: float, alpha: float = 0.01) -> float:
    # E[-R | R <= quantile] = -mu + sigma * phi(z_alpha) / alpha
    return -mu + sigma * norm.pdf(norm.ppf(alpha)) / alpha


# --- Volatilité EWMA (RiskMetrics) : les jours récents pèsent plus ----------

def ewma_volatility(returns: pd.Series, lam: float = 0.94) -> pd.Series:
    """sigma²_t = lam * sigma²_{t-1} + (1 - lam) * r²_{t-1}.

    La valeur à la date t n'utilise que les rendements jusqu'à t - 1 : c'est
    une prévision pour le jour t.
    """
    r2 = returns.pow(2).shift(1)
    var = r2.ewm(alpha=1 - lam, adjust=False).mean()
    return np.sqrt(var)


# --- Prévisions glissantes, jour par jour, sans regarder le futur -----------

def rolling_var(returns: pd.Series, method: str, window: int = 250, alpha: float = 0.01,
                lam: float = 0.94, fhs_window: int = 500) -> pd.Series:
    """Prévision de VaR à 1 jour pour chaque date t, calculée avec les données
    jusqu'à t - 1 seulement (comme un gestionnaire de risque le ferait le
    matin, avant l'ouverture).

    method : "historical", "normal", "ewma", "fhs" ou "garch_t".

    fhs (simulation historique filtrée) : on divise chaque rendement passé par
    la volatilité EWMA de son jour (rendement « standardisé »), on prend le
    quantile historique de ces rendements standardisés sur `fhs_window` jours,
    puis on le multiplie par la volatilité prévue pour demain. On garde ainsi
    la forme réelle des queues (historique) tout en réagissant vite aux
    changements de volatilité (EWMA).
    """
    past = returns.shift(1)
    if method == "historical":
        out = past.rolling(window).quantile(alpha, interpolation="linear").mul(-1)
    elif method == "normal":
        mu, sigma = past.rolling(window).mean(), past.rolling(window).std()
        out = -(mu + sigma * norm.ppf(alpha))
    elif method == "ewma":
        # moyenne supposée nulle à un jour, convention RiskMetrics
        sigma = ewma_volatility(returns, lam)
        out = -sigma * norm.ppf(alpha)
        out.iloc[:window] = np.nan  # même période d'apprentissage que les autres
    elif method == "fhs":
        sigma = ewma_volatility(returns, lam)
        z = (returns / sigma).shift(1)  # rendements standardisés, jusqu'à t - 1
        out = -z.rolling(fhs_window).quantile(alpha, interpolation="linear") * sigma
    elif method == "garch_t":
        from .garch import garch_var_forecast
        out = garch_var_forecast(returns, alpha)
    else:
        raise ValueError("method : 'historical', 'normal', 'ewma', 'fhs' ou 'garch_t'")
    return out.rename(method)


def scale_to_horizon(var_1d: float, days: int) -> float:
    """Règle de la racine du temps (valable si les jours sont indépendants)."""
    return var_1d * math.sqrt(days)
