import numpy as np
import pytest

from pricer import (
    bs_greeks,
    bs_price,
    geometric_asian_price,
    mc_asian,
    mc_european,
    mc_greeks,
)

P = dict(S=100.0, K=105.0, T=1.0, r=0.05, sigma=0.25, q=0.01)

# Écart toléré en nombre d'erreurs types : 4 sigma -> ~6e-5 de faux échecs
# par test pour une graine donnée ; les graines sont fixées, donc déterministe.
N_SE = 4


@pytest.mark.parametrize("kind", ["call", "put"])
@pytest.mark.parametrize(
    "antithetic,control_variate", [(False, False), (True, False), (False, True), (True, True)]
)
def test_mc_converges_to_black_scholes(kind, antithetic, control_variate):
    res = mc_european(**P, kind=kind, n_paths=200_000, seed=1,
                      antithetic=antithetic, control_variate=control_variate)
    assert abs(res.price - bs_price(**P, kind=kind)) < N_SE * res.std_error


def test_error_decreases_as_one_over_sqrt_n():
    """Pente log(erreur type) / log(N) ~ -1/2."""
    ns = np.array([1_000, 4_000, 16_000, 64_000, 256_000])
    se = [mc_european(**P, n_paths=int(n), seed=7).std_error for n in ns]
    slope = np.polyfit(np.log(ns), np.log(se), 1)[0]
    assert slope == pytest.approx(-0.5, abs=0.02)


def test_variance_reduction_at_equal_cost():
    kw = dict(**P, n_paths=100_000, seed=3)
    plain = mc_european(**kw).std_error
    anti = mc_european(**kw, antithetic=True).std_error
    cv = mc_european(**kw, control_variate=True).std_error
    both = mc_european(**kw, antithetic=True, control_variate=True).std_error
    assert anti < plain
    assert cv < plain
    assert both < min(anti, cv)


def test_mc_greeks_close_to_analytic():
    mc = mc_greeks(**P, n_paths=400_000, seed=11)
    exact = bs_greeks(**P)
    assert mc["delta"] == pytest.approx(exact["delta"], rel=1e-2)
    assert mc["gamma"] == pytest.approx(exact["gamma"], rel=5e-2)
    assert mc["vega"] == pytest.approx(exact["vega"], rel=2e-2)


@pytest.mark.parametrize("kind", ["call", "put"])
def test_geometric_asian_mc_matches_closed_form(kind):
    res = mc_asian(**P, n_steps=12, kind=kind, n_paths=200_000, seed=5, average="geometric")
    exact = geometric_asian_price(**P, n_steps=12, kind=kind)
    assert abs(res.price - exact) < N_SE * res.std_error


def test_geometric_asian_one_step_is_european():
    # Avec une seule date d'observation (t = T), la moyenne vaut S_T.
    for kind in ("call", "put"):
        assert geometric_asian_price(**P, n_steps=1, kind=kind) == pytest.approx(
            bs_price(**P, kind=kind), abs=1e-12
        )


def test_arithmetic_asian_control_variate():
    kw = dict(**P, n_steps=12, n_paths=100_000, seed=9)
    plain = mc_asian(**kw)
    cv = mc_asian(**kw, control_variate=True)
    # Même prix (à l'erreur près) et erreur type divisée par plus de 10
    assert abs(plain.price - cv.price) < N_SE * plain.std_error
    assert cv.std_error < plain.std_error / 10
    # Moyenne arithmétique >= moyenne géométrique -> call arithmétique plus cher
    assert cv.price > geometric_asian_price(**P, n_steps=12)


def test_ci95_contains_price():
    res = mc_european(**P, n_paths=10_000, seed=2)
    lo, hi = res.ci95
    assert lo < res.price < hi
