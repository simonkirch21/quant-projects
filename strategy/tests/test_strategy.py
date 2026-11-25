import math

import numpy as np
import pandas as pd
import pytest

from strategy.portfolio import run_portfolio
from strategy.robustness import (
    block_bootstrap_sharpe, block_bootstrap_sharpe_diff, deflated_sharpe_ratio,
    expected_max_sharpe, probabilistic_sharpe_ratio,
)
from strategy.signals import target_weights, vol_scale
from strategy.walkforward import walk_forward


def random_prices(n=3_000, cols=("A", "B", "C"), seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n)
    vols = np.array([0.01, 0.005, 0.02])[: len(cols)]
    rets = rng.normal(0.0002, vols, (n, len(cols)))
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=idx, columns=list(cols))


# --- Signaux -----------------------------------------------------------------

def test_vol_scale_targets_volatility_and_caps_leverage():
    p = random_prices()
    s_calm = vol_scale(p["B"], target_vol=0.10).iloc[-500:]   # ~8 % de vol annuelle -> plafond 1
    s_wild = vol_scale(p["C"], target_vol=0.10).iloc[-500:]   # ~32 % -> ~0,31
    assert (s_calm <= 1.0).all() and s_calm.mean() > 0.95
    assert s_wild.mean() == pytest.approx(0.10 / (0.02 * math.sqrt(252)), rel=0.1)


def test_weights_are_long_only_and_never_levered():
    w = target_weights(random_prices(), window=100)
    assert (w >= 0).all().all()
    assert (w.sum(axis=1) <= 1 + 1e-12).all()


def test_volatility_targeting_equalises_risk():
    """Après ciblage, chaque actif apporte à peu près la même volatilité,
    alors que leurs volatilités brutes vont du simple au quadruple."""
    p = random_prices()
    w = target_weights(p, window=100, target_vol=0.04, use_trend=False)
    contrib = (w.shift(1) * p.pct_change()).iloc[300:].std()
    assert contrib.max() / contrib.min() < 1.3


# --- Portefeuille --------------------------------------------------------------

def test_constant_weights_portfolio_matches_weighted_returns():
    p = random_prices()
    w = pd.DataFrame({"A": 0.5, "B": 0.3, "C": 0.2}, index=p.index)
    port = run_portfolio(p, w, cost=0.0)
    expected = (p.pct_change() * w.shift(1)).sum(axis=1)
    assert port.iloc[1:].to_numpy() == pytest.approx(expected.iloc[1:].to_numpy(), abs=1e-15)


# --- Walk-forward ----------------------------------------------------------------

def test_walk_forward_never_uses_the_test_year():
    """Le paramètre 1 est excellent jusqu'en 2004 puis catastrophique ; le 2 est
    l'inverse. Le walk-forward doit choisir 1 pour 2005 (il ne pouvait pas
    savoir) et subir sa perte."""
    idx = pd.bdate_range("2000-01-03", "2005-12-30")
    good_then_bad = pd.Series(np.where(idx.year < 2005, 0.001, -0.002), index=idx)
    bad_then_good = pd.Series(np.where(idx.year < 2005, -0.001, 0.002), index=idx)
    noise = np.random.default_rng(0).normal(0, 0.001, len(idx))
    oos, chosen = walk_forward({1: good_then_bad + noise, 2: bad_then_good + noise}, 2005, 2005)
    assert chosen[2005] == 1
    assert oos.mean() < 0


def test_walk_forward_output_covers_only_test_years():
    idx = pd.bdate_range("2000-01-03", "2010-12-31")
    rng = np.random.default_rng(1)
    rb = {k: pd.Series(rng.normal(0, 0.01, len(idx)), index=idx) for k in (1, 2, 3)}
    oos, chosen = walk_forward(rb, 2006, 2010)
    assert oos.index.min().year == 2006 and oos.index.max().year == 2010
    assert oos.index.is_unique and len(oos) == len(idx[idx.year >= 2006])
    assert list(chosen.index) == list(range(2006, 2011))


# --- Robustesse statistique ------------------------------------------------------

def test_psr_is_one_half_at_observed_sharpe():
    r = pd.Series(np.random.default_rng(2).normal(0.0005, 0.01, 5_000))
    assert probabilistic_sharpe_ratio(r, r.mean() / r.std()) == pytest.approx(0.5, abs=1e-9)


def test_expected_max_sharpe_grows_with_number_of_trials():
    vals = [expected_max_sharpe(0.01, n) for n in (2, 10, 100, 1_000)]
    assert vals == sorted(vals) and vals[0] > 0


def test_deflated_sharpe_catches_lucky_noise():
    """100 stratégies sans aucun talent (bruit pur). La meilleure a un Sharpe
    brut flatteur et un PSR élevé ; le DSR, qui tient compte des 100 essais,
    ne s'y laisse pas prendre."""
    rng = np.random.default_rng(3)
    trials = [pd.Series(rng.normal(0, 0.01, 1_260)) for _ in range(100)]   # 5 ans chacune
    srs = [t.mean() / t.std() for t in trials]
    best = trials[int(np.argmax(srs))]
    assert max(srs) * math.sqrt(252) > 0.6
    assert probabilistic_sharpe_ratio(best, 0.0) > 0.9
    assert deflated_sharpe_ratio(best, srs) < 0.6


def test_bootstrap_interval_covers_true_sharpe():
    mu, sigma = 0.0004, 0.01
    r = pd.Series(np.random.default_rng(4).normal(mu, sigma, 5_000))
    lo, hi = np.percentile(block_bootstrap_sharpe(r, n_boot=500), [2.5, 97.5])
    assert lo < mu / sigma * math.sqrt(252) < hi


def test_paired_bootstrap_of_identical_strategies_is_zero():
    r = pd.Series(np.random.default_rng(5).normal(0.0003, 0.01, 2_000))
    assert np.allclose(block_bootstrap_sharpe_diff(r, r, n_boot=200), 0.0)
