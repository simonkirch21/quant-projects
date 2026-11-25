import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from riskmodel.backtest import basel_zone, christoffersen_independence, exceptions, kupiec_pof
from riskmodel.portfolio import portfolio_returns, risk_contributions
from riskmodel.var import (
    historical_es, historical_var, normal_es, normal_var, rolling_var, scale_to_horizon,
)

METHODS = ["historical", "normal", "ewma", "fhs"]


def normal_returns(n=4_000, sigma=0.01, seed=0):
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0, sigma, n), index=pd.bdate_range("2000-01-03", periods=n))


def test_normal_var_and_es_reference_values():
    # Loi normale centrée réduite à 99 % : VaR = 2,326 ; ES = phi(2,326) / 0,01 = 2,665
    assert normal_var(0, 1, 0.01) == pytest.approx(2.3263, abs=1e-4)
    assert normal_es(0, 1, 0.01) == pytest.approx(2.6652, abs=1e-4)


def test_historical_matches_normal_on_normal_data():
    r = np.random.default_rng(1).normal(0, 0.01, 1_000_000)
    assert historical_var(r) == pytest.approx(normal_var(0, 0.01), rel=0.01)
    assert historical_es(r) == pytest.approx(normal_es(0, 0.01), rel=0.01)


def test_es_is_beyond_var():
    r = np.random.default_rng(2).standard_t(3, 10_000) * 0.01
    assert historical_es(r) > historical_var(r)


def test_square_root_of_time():
    assert scale_to_horizon(0.02, 10) == pytest.approx(0.02 * 10**0.5)


@pytest.mark.parametrize("method", METHODS)
def test_forecast_uses_only_the_past(method):
    """Modifier le rendement du jour t ne doit pas changer la prévision du jour t."""
    r = normal_returns()
    shocked = r.copy()
    shocked.iloc[-1] = -0.5
    a, b = rolling_var(r, method), rolling_var(shocked, method)
    assert a.iloc[-1] == pytest.approx(b.iloc[-1], rel=1e-12)


@pytest.mark.parametrize("method", ["historical", "normal"])
def test_long_window_passes_kupiec_on_iid_normal_data(method):
    """Sur des données vraiment normales, avec assez d'historique, le taux de
    dépassement doit être compatible avec 1 %."""
    r = normal_returns(n=8_000, seed=3)
    e = exceptions(r, rolling_var(r, method, window=1_000))
    assert kupiec_pof(len(e), int(e.sum()))["p_value"] > 0.05


@pytest.mark.parametrize("method", METHODS)
def test_exception_rate_is_plausible_on_iid_normal_data(method):
    r = normal_returns(n=6_000, seed=3)
    rate = exceptions(r, rolling_var(r, method)).mean()
    assert 0.007 < rate < 0.016


def test_short_historical_window_underestimates_risk():
    """Erreur d'estimation : le 1 % des pires jours estimé sur 250 jours (2 ou 3
    observations) est trop optimiste en moyenne. Même sur des données
    parfaitement normales, la VaR historique 250 jours est dépassée plus de 1 %
    du temps ; sur 1 000 jours, l'écart disparaît presque."""
    def mean_rate(window):
        return np.mean([
            exceptions(r, rolling_var(r, "historical", window=window)).mean()
            for r in (normal_returns(n=6_000, seed=s) for s in range(20))
        ])
    short, long_ = mean_rate(250), mean_rate(1_000)
    assert short > 0.012
    assert abs(long_ - 0.01) < abs(short - 0.01)


def test_kupiec_values():
    # Exactement le nombre attendu -> statistique nulle
    assert kupiec_pof(1_000, 10)["LR"] == pytest.approx(0, abs=1e-12)
    # 10 dépassements sur 250 jours (2,5 attendus) -> rejet ; 3 -> accepté
    assert kupiec_pof(250, 10)["p_value"] < 0.01
    assert kupiec_pof(250, 3)["p_value"] > 0.5


def test_christoffersen_detects_clusters():
    rng = np.random.default_rng(4)
    spread = pd.Series(rng.random(5_000) < 0.02)
    clustered = pd.Series(np.zeros(5_000, dtype=bool))
    for start in range(100, 5_000, 500):       # 10 grappes de 10 jours
        clustered.iloc[start:start + 10] = True
    assert christoffersen_independence(spread)["p_value"] > 0.05
    assert christoffersen_independence(clustered)["p_value"] < 1e-6


def test_basel_zones():
    assert [basel_zone(x) for x in (0, 4, 5, 9, 10)] == ["vert", "vert", "orange", "orange", "rouge"]


def test_risk_contributions_add_up():
    rng = np.random.default_rng(5)
    cov = np.array([[1.0, 0.3, -0.2], [0.3, 0.5, 0.1], [-0.2, 0.1, 0.8]]) * 1e-4
    R = pd.DataFrame(rng.multivariate_normal([0, 0, 0], cov, 50_000), columns=["A", "B", "C"])
    w = {"A": 0.5, "B": 0.3, "C": 0.2}
    rc = risk_contributions(R, w)
    sigma_p = portfolio_returns(R, w).std()
    assert rc["contribution VaR"].sum() == pytest.approx(-norm.ppf(0.01) * sigma_p, rel=1e-9)
    assert rc["part du risque"].sum() == pytest.approx(1.0, rel=1e-12)
