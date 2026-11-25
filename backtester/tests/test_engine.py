import numpy as np
import pandas as pd
import pytest

from backtester.engine import positions_from_signal, run_backtest
from backtester.strategies import buy_and_hold, sma_trend


def random_prices(n=2_000, seed=0):
    """Prix simulés (marche aléatoire) : les tests n'ont pas besoin d'internet."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n))), index=idx)


def test_signal_is_shifted_by_one_day():
    sig = pd.Series([0.0, 1.0, 1.0, 0.0, 1.0])
    assert positions_from_signal(sig).tolist() == [0.0, 0.0, 1.0, 1.0, 0.0]


def test_no_look_ahead_on_perfect_foresight_signal():
    """Signal « le marché a monté aujourd'hui » : sans décalage, il gagnerait
    sur chaque hausse et deviendrait milliardaire. Avec le décalage, il ne
    doit rien avoir d'extraordinaire."""
    p = random_prices()
    signal = (p.pct_change() > 0).astype(float)
    cheat = (1 + signal * p.pct_change().fillna(0)).prod()
    honest = run_backtest(p, signal, cost=0.0)["equity"].iloc[-1]
    buy_hold = p.iloc[-1] / p.iloc[0]
    assert cheat > 1_000 * buy_hold          # la triche explose
    assert honest < 3 * buy_hold             # la version honnête reste raisonnable


def test_buy_and_hold_matches_price_ratio_minus_one_trade():
    p = random_prices()
    cost = 0.001
    eq = run_backtest(p, buy_and_hold(p), cost=cost)["equity"]
    # Signal du jour 0 -> achat à la clôture du jour 0 : on gagne tout le
    # parcours p[0] -> p[-1]. L'unique achat est déduit du rendement du jour 1.
    r1 = p.iloc[1] / p.iloc[0] - 1
    expected = (1 + r1 - cost) * p.iloc[-1] / p.iloc[1]
    assert eq.iloc[-1] == pytest.approx(expected, rel=1e-12)


def test_always_cash_stays_at_one():
    p = random_prices()
    eq = run_backtest(p, pd.Series(0.0, index=p.index), cost=0.001)["equity"]
    assert (eq == 1.0).all()


def test_costs_are_paid_on_each_change_only():
    p = pd.Series([100.0, 100, 100, 100, 100, 100], index=pd.bdate_range("2020-01-01", periods=6))
    sig = pd.Series([1.0, 1, 0, 0, 1, 1], index=p.index)   # achat, vente, achat
    bt = run_backtest(p, sig, cost=0.01)
    assert bt["turnover"].sum() == 3
    # Prix plat : la seule perte vient des 3 transactions à 1 %.
    assert bt["equity"].iloc[-1] == pytest.approx(0.99**3)


def test_costs_reduce_performance():
    p = random_prices()
    sig = sma_trend(p, 50)
    free = run_backtest(p, sig, cost=0.0)["equity"].iloc[-1]
    paid = run_backtest(p, sig, cost=0.005)["equity"].iloc[-1]
    n_trades = run_backtest(p, sig, cost=0.0)["turnover"].sum()
    assert paid < free
    assert paid == pytest.approx(free, rel=0.005 * n_trades + 0.01)


def test_minus_50_plus_50_is_a_loss():
    p = pd.Series([100.0, 100.0, 50.0, 75.0], index=pd.bdate_range("2020-01-01", periods=4))
    eq = run_backtest(p, pd.Series(1.0, index=p.index), cost=0.0)["equity"]
    assert eq.iloc[-1] == pytest.approx(0.75)


def test_sma_is_flat_before_enough_history():
    p = random_prices(300)
    sig = sma_trend(p, 200)
    assert (sig.iloc[:199] == 0).all()
