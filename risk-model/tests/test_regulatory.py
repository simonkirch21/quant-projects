import math

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm
from scipy.stats import t as student_t

from riskmodel.evt import evt_es, evt_var, fit_pot
from riskmodel.garch import fit_garch_t, garch_variance, student_quantile
from riskmodel.regulatory import (
    market_risk_capital, overlapping_returns, plus_factor, stressed_period,
)
from riskmodel.stress import hypothetical_stress, portfolio_pnl, reverse_stress, scenario_returns

W = {"A": 0.5, "B": 0.3, "C": 0.2}


# --- Stress tests ----------------------------------------------------------------

def test_portfolio_pnl_is_weighted_sum():
    assert portfolio_pnl(W, {"A": -0.2, "B": 0.1, "C": 0.0}) == pytest.approx(-0.07)


def test_scenario_returns_compound_between_two_closes():
    idx = pd.bdate_range("2020-01-01", periods=4)
    R = pd.DataFrame({"A": [0.5, 0.10, -0.10, 0.0]}, index=idx)   # le 1er jour est exclu
    assert scenario_returns(R, idx[0], idx[-1])["A"] == pytest.approx(1.10 * 0.90 - 1)


def test_hypothetical_stress_table():
    t = hypothetical_stress(W, {"choc": {"A": -0.3, "B": 0.1, "C": 0.0}})
    assert t.loc["choc", "portefeuille"] == pytest.approx(-0.12)


def test_reverse_stress_hits_the_loss_with_the_most_plausible_shock():
    rng = np.random.default_rng(0)
    cov = pd.DataFrame(np.array([[4, 1, 0.5], [1, 2, -0.3], [0.5, -0.3, 3]]) * 1e-4,
                       index=list(W), columns=list(W))
    res = reverse_stress(cov, W, loss=0.05)
    x = res["chocs"].to_numpy()
    w = np.array(list(W.values()))
    inv = np.linalg.inv(cov.to_numpy())
    assert w @ x == pytest.approx(-0.05)
    d_best = x @ inv @ x
    for _ in range(200):   # tout autre choc donnant la même perte est moins plausible
        y = rng.normal(0, 0.05, 3)
        y = y - (w @ y + 0.05) / (w @ w) * w
        assert y @ inv @ y >= d_best - 1e-12
    assert res["écarts-types"] == pytest.approx(math.sqrt(d_best))


# --- Réglementaire ---------------------------------------------------------------

def test_plus_factor_table():
    assert [plus_factor(n) for n in (0, 4, 5, 7, 9, 12)] == [0, 0, 0.40, 0.65, 0.85, 1.0]


def test_market_risk_capital():
    c = market_risk_capital(var_10d=0.05, svar_10d=0.10, n_exceptions_250=6)
    assert c["multiplicateur"] == 3.5
    assert c["capital"] == pytest.approx(3.5 * 0.15)


def test_overlapping_returns():
    r = pd.Series([0.1, -0.1, 0.2, 0.0])
    assert overlapping_returns(r, 2).tolist() == pytest.approx([1.1 * 0.9 - 1, 0.9 * 1.2 - 1, 0.2])


def test_stressed_period_finds_the_crisis():
    rng = np.random.default_rng(1)
    idx = pd.bdate_range("2000-01-03", periods=3_000)
    r = pd.Series(rng.normal(0, 0.005, 3_000), index=idx)
    r.iloc[1_500:1_700] = rng.normal(0, 0.03, 200)          # crise injectée
    start, end = stressed_period(r, window=250)
    overlap = len(r.loc[max(start, idx[1_500]):min(end, idx[1_699])])
    assert overlap >= 150        # la fenêtre retenue est surtout faite de jours de crise


# --- GARCH -----------------------------------------------------------------------

def test_garch_variance_matches_the_recursion():
    r = np.random.default_rng(2).normal(0, 0.01, 100)
    v = garch_variance(r, 2e-6, 0.08, 0.9)
    expected = [r.var()]
    for x in r:
        expected.append(2e-6 + 0.08 * x * x + 0.9 * expected[-1])
    assert v == pytest.approx(expected, rel=1e-12)


def test_garch_fit_recovers_simulated_parameters():
    rng = np.random.default_rng(3)
    omega, a, b, nu, n = 2e-6, 0.08, 0.90, 6.0, 30_000
    z = student_t.rvs(nu, size=n, random_state=rng) * math.sqrt((nu - 2) / nu)
    r, var = np.empty(n), omega / (1 - a - b)
    for i in range(n):
        r[i] = math.sqrt(var) * z[i]
        var = omega + a * r[i] ** 2 + b * var
    p = fit_garch_t(r)
    assert p["a"] == pytest.approx(a, abs=0.02)
    assert p["b"] == pytest.approx(b, abs=0.03)
    assert p["nu"] == pytest.approx(nu, abs=1.5)


def test_student_quantile_has_unit_variance_scaling():
    # Plus nu est grand, plus on retrouve la loi normale (2,326 à 1 %)
    assert student_quantile(0.01, 1_000) == pytest.approx(-2.326, abs=0.01)
    # À variance égale, la Student a moins de jours « moyennement mauvais » (5 %)…
    assert student_quantile(0.05, 4) > student_quantile(0.05, 1_000)
    # …et plus de jours extrêmes (1 % et au-delà) : ce sont les queues épaisses
    assert student_quantile(0.01, 4) < student_quantile(0.01, 1_000)
    assert student_quantile(0.001, 4) < student_quantile(0.001, 1_000)


# --- Valeurs extrêmes --------------------------------------------------------------

def test_evt_estimates_extreme_quantiles_of_fat_tailed_data():
    nu = 4
    x = student_t.rvs(nu, size=200_000, random_state=np.random.default_rng(4))
    fit = fit_pot(x, 0.95)
    # Théorie : xi = 1 / nu = 0,25. L'estimation à un seuil fini est biaisée vers le bas
    # (convergence lente pour la Student), mais signale bien des queues épaisses.
    assert 0.1 < fit["xi"] < 0.35
    sigma = x.std()
    for level in (0.999, 0.9999):
        true_q = student_t.ppf(level, nu)
        normal_q = sigma * norm.ppf(level)
        assert abs(evt_var(fit, level) / true_q - 1) < 0.10      # EVT : moins de 10 % d'erreur
        assert abs(normal_q / true_q - 1) > 0.25                 # loi normale : très loin
    assert evt_es(fit, 0.999) > evt_var(fit, 0.999)
