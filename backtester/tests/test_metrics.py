import math

import numpy as np
import pandas as pd
import pytest

from backtester.metrics import (
    TRADING_DAYS, annual_volatility, cagr, drawdown, max_drawdown, sharpe_ratio,
)


def test_cagr_of_constant_daily_return():
    r = 0.0004
    eq = pd.Series((1 + r) ** np.arange(TRADING_DAYS * 5 + 1))
    assert cagr(eq) == pytest.approx((1 + r) ** TRADING_DAYS - 1, rel=1e-12)


def test_cagr_doubling_in_ten_years():
    eq = pd.Series(np.linspace(1, 2, TRADING_DAYS * 10 + 1))
    assert cagr(eq) == pytest.approx(2 ** 0.1 - 1, rel=1e-12)


def test_max_drawdown_hand_example():
    # sommet 2, creux 1 -> -50 % ; puis nouveau sommet 3, creux 2,4 -> -20 %
    eq = pd.Series([1.0, 2.0, 1.0, 3.0, 2.4])
    assert max_drawdown(eq) == pytest.approx(-0.5)
    assert drawdown(eq).tolist() == pytest.approx([0, 0, -0.5, 0, -0.2])


def test_volatility_scales_with_sqrt_time():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0, 0.01, 200_000))
    assert annual_volatility(r) == pytest.approx(0.01 * math.sqrt(TRADING_DAYS), rel=0.01)


def test_sharpe_of_known_series():
    rng = np.random.default_rng(2)
    mu, sigma = 0.0005, 0.01
    r = pd.Series(rng.normal(mu, sigma, 500_000))
    expected = mu / sigma * math.sqrt(TRADING_DAYS)   # ~0,79
    assert sharpe_ratio(r) == pytest.approx(expected, abs=0.05)


def test_sharpe_zero_volatility():
    assert sharpe_ratio(pd.Series([0.0] * 10)) == 0.0
