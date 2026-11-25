"""Pricing Monte Carlo sous mouvement brownien géométrique (risque neutre).

    dS = (r - q) S dt + sigma S dW
    S_T = S exp((r - q - sigma²/2) T + sigma sqrt(T) Z),   Z ~ N(0, 1)

Contenu :
    - options européennes, avec deux réductions de variance :
        * variables antithétiques (Z et -Z)
        * variable de contrôle : S_T actualisé, d'espérance connue S e^{-qT}
    - grecques par différences finies avec nombres aléatoires communs
    - options asiatiques arithmétiques (moyenne discrète), avec l'asiatique
      géométrique comme variable de contrôle (elle a une formule fermée)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

Z_95 = 1.959963984540054  # quantile 97,5 % de la loi normale


@dataclass(frozen=True)
class MCResult:
    price: float
    std_error: float
    n_paths: int

    @property
    def ci95(self) -> tuple[float, float]:
        """Intervalle de confiance à 95 %."""
        return self.price - Z_95 * self.std_error, self.price + Z_95 * self.std_error


def _payoff(ST: np.ndarray, K: float, kind: str) -> np.ndarray:
    kind = kind.lower()
    if kind == "call":
        return np.maximum(ST - K, 0.0)
    if kind == "put":
        return np.maximum(K - ST, 0.0)
    raise ValueError("kind doit valoir 'call' ou 'put'")


def _control_variate(y: np.ndarray, x: np.ndarray, x_mean: float) -> np.ndarray:
    """Y - b (X - E[X]) avec b = Cov(X, Y) / Var(X) estimé sur l'échantillon."""
    var_x = np.var(x)
    if var_x == 0:
        return y
    b = np.cov(x, y, bias=True)[0, 1] / var_x
    return y - b * (x - x_mean)


def _summarize(samples: np.ndarray, n_paths: int) -> MCResult:
    return MCResult(
        price=float(samples.mean()),
        std_error=float(samples.std(ddof=1) / math.sqrt(samples.size)),
        n_paths=n_paths,
    )


def _terminal(S, T, r, sigma, q, z):
    return S * np.exp((r - q - 0.5 * sigma**2) * T + sigma * math.sqrt(T) * z)


def mc_european(
    S, K, T, r, sigma, kind="call", q=0.0, n_paths=100_000, seed=None,
    antithetic=False, control_variate=False, z=None,
) -> MCResult:
    """Prix Monte Carlo d'une option européenne.

    Avec antithetic=True, n_paths est le nombre total de trajectoires
    (n_paths // 2 paires) : la comparaison avec le Monte Carlo simple se fait
    donc à coût égal. L'erreur type est calculée sur les moyennes de paires,
    qui sont indépendantes entre elles.

    z : tirages normaux fournis par l'appelant (nombres aléatoires communs).
    """
    if z is None:
        rng = np.random.default_rng(seed)
        z = rng.standard_normal(n_paths // 2 if antithetic else n_paths)
    disc = math.exp(-r * T)

    if antithetic:
        st_plus, st_minus = _terminal(S, T, r, sigma, q, z), _terminal(S, T, r, sigma, q, -z)
        y = 0.5 * disc * (_payoff(st_plus, K, kind) + _payoff(st_minus, K, kind))
        x = 0.5 * disc * (st_plus + st_minus)
    else:
        st = _terminal(S, T, r, sigma, q, z)
        y = disc * _payoff(st, K, kind)
        x = disc * st

    if control_variate:
        y = _control_variate(y, x, S * math.exp(-q * T))

    return _summarize(y, n_paths)


def mc_greeks(
    S, K, T, r, sigma, kind="call", q=0.0, n_paths=200_000, seed=None,
    rel_bump_s=0.01, bump_sigma=0.01,
) -> dict:
    """Delta, gamma et vega par différences finies centrées.

    Les mêmes tirages Z servent à tous les prix (nombres aléatoires communs) :
    sans ça, le bruit Monte Carlo écraserait la petite différence de prix.
    """
    z = np.random.default_rng(seed).standard_normal(n_paths // 2)

    def price(s, vol):
        return mc_european(s, K, T, r, vol, kind, q, n_paths, antithetic=True, z=z).price

    h = rel_bump_s * S
    p_mid, p_up, p_down = price(S, sigma), price(S + h, sigma), price(S - h, sigma)
    return {
        "delta": (p_up - p_down) / (2 * h),
        "gamma": (p_up - 2 * p_mid + p_down) / h**2,
        "vega": (price(S, sigma + bump_sigma) - price(S, sigma - bump_sigma)) / (2 * bump_sigma),
    }


def geometric_asian_price(S, K, T, r, sigma, n_steps, kind="call", q=0.0) -> float:
    """Prix fermé d'une asiatique à moyenne géométrique discrète.

    Moyenne sur les dates t_i = i T / n, i = 1..n. ln G suit une loi normale :
        m  = ln S + (r - q - sigma²/2) T (n + 1) / (2n)
        v² = sigma² T (n + 1)(2n + 1) / (6 n²)
    """
    n = n_steps
    m = math.log(S) + (r - q - 0.5 * sigma**2) * T * (n + 1) / (2 * n)
    v = sigma * math.sqrt(T * (n + 1) * (2 * n + 1) / (6 * n**2))
    d1 = (m - math.log(K) + v**2) / v
    d2 = d1 - v
    fwd = math.exp(m + 0.5 * v**2)  # E[G]
    disc = math.exp(-r * T)
    if kind.lower() == "call":
        return disc * (fwd * norm.cdf(d1) - K * norm.cdf(d2))
    if kind.lower() == "put":
        return disc * (K * norm.cdf(-d2) - fwd * norm.cdf(-d1))
    raise ValueError("kind doit valoir 'call' ou 'put'")


def _gbm_paths(S, T, r, sigma, q, n_steps, z):
    """Trajectoires aux dates t_1..t_n (z de forme (n_paths, n_steps))."""
    dt = T / n_steps
    increments = (r - q - 0.5 * sigma**2) * dt + sigma * math.sqrt(dt) * z
    return S * np.exp(np.cumsum(increments, axis=1))


def mc_asian(
    S, K, T, r, sigma, n_steps=12, kind="call", q=0.0, n_paths=100_000, seed=None,
    average="arithmetic", control_variate=False,
) -> MCResult:
    """Asiatique à moyenne discrète (arithmétique ou géométrique).

    control_variate=True (moyenne arithmétique seulement) : l'asiatique
    géométrique, très corrélée et de prix connu, sert de variable de contrôle.
    """
    z = np.random.default_rng(seed).standard_normal((n_paths, n_steps))
    paths = _gbm_paths(S, T, r, sigma, q, n_steps, z)
    disc = math.exp(-r * T)

    geo_mean = np.exp(np.log(paths).mean(axis=1))
    if average == "geometric":
        return _summarize(disc * _payoff(geo_mean, K, kind), n_paths)
    if average != "arithmetic":
        raise ValueError("average doit valoir 'arithmetic' ou 'geometric'")

    y = disc * _payoff(paths.mean(axis=1), K, kind)
    if control_variate:
        x = disc * _payoff(geo_mean, K, kind)
        y = _control_variate(y, x, geometric_asian_price(S, K, T, r, sigma, n_steps, kind, q))
    return _summarize(y, n_paths)
