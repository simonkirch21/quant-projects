import math

import pytest

from pricer import bs_greeks, bs_price, implied_vol

# Exemple de référence (Hull, Options, Futures and Other Derivatives) :
# S=42, K=40, r=10 %, sigma=20 %, T=6 mois -> call 4,76 ; put 0,81
HULL = dict(S=42.0, K=40.0, T=0.5, r=0.10, sigma=0.20)

CASES = [
    dict(S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.20, q=0.0),
    dict(S=100.0, K=120.0, T=0.25, r=0.03, sigma=0.35, q=0.02),
    dict(S=80.0, K=60.0, T=2.0, r=0.01, sigma=0.15, q=0.04),
]


def test_reference_values_hull():
    assert bs_price(**HULL, kind="call") == pytest.approx(4.76, abs=5e-3)
    assert bs_price(**HULL, kind="put") == pytest.approx(0.81, abs=5e-3)


@pytest.mark.parametrize("p", CASES)
def test_put_call_parity(p):
    # C - P = S e^{-qT} - K e^{-rT}
    c, put = bs_price(**p, kind="call"), bs_price(**p, kind="put")
    expected = p["S"] * math.exp(-p["q"] * p["T"]) - p["K"] * math.exp(-p["r"] * p["T"])
    assert c - put == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("p", CASES)
@pytest.mark.parametrize("kind", ["call", "put"])
def test_no_arbitrage_bounds(p, kind):
    S, K, T, r, q = p["S"], p["K"], p["T"], p["r"], p["q"]
    price = bs_price(**p, kind=kind)
    fwd_s, fwd_k = S * math.exp(-q * T), K * math.exp(-r * T)
    if kind == "call":
        assert max(fwd_s - fwd_k, 0) <= price <= fwd_s
    else:
        assert max(fwd_k - fwd_s, 0) <= price <= fwd_k


@pytest.mark.parametrize("p", CASES)
@pytest.mark.parametrize("kind", ["call", "put"])
def test_greeks_match_finite_differences(p, kind):
    """Grecques analytiques = dérivées numériques de la formule fermée."""
    g = bs_greeks(**p, kind=kind)

    def price(**over):
        return bs_price(**{**p, **over}, kind=kind)

    hs, hv, hr, ht = 1e-3 * p["S"], 1e-4, 1e-5, 1e-5
    fd = {
        "delta": (price(S=p["S"] + hs) - price(S=p["S"] - hs)) / (2 * hs),
        "gamma": (price(S=p["S"] + hs) - 2 * price() + price(S=p["S"] - hs)) / hs**2,
        "vega": (price(sigma=p["sigma"] + hv) - price(sigma=p["sigma"] - hv)) / (2 * hv),
        "rho": (price(r=p["r"] + hr) - price(r=p["r"] - hr)) / (2 * hr),
        # theta = dV/dt = -dV/dT
        "theta": -(price(T=p["T"] + ht) - price(T=p["T"] - ht)) / (2 * ht),
    }
    for name, value in fd.items():
        assert g[name] == pytest.approx(value, rel=1e-4, abs=1e-6), name


@pytest.mark.parametrize("p", CASES)
@pytest.mark.parametrize("kind", ["call", "put"])
def test_implied_vol_round_trip(p, kind):
    price = bs_price(**p, kind=kind)
    args = {k: v for k, v in p.items() if k != "sigma"}
    assert implied_vol(price, **args, kind=kind) == pytest.approx(p["sigma"], abs=1e-8)


def test_implied_vol_rejects_arbitrage_price():
    with pytest.raises(ValueError):
        implied_vol(50.0, S=42, K=40, T=0.5, r=0.1, kind="call")  # > S


def test_invalid_inputs():
    with pytest.raises(ValueError):
        bs_price(100, 100, 0.0, 0.05, 0.2)
    with pytest.raises(ValueError):
        bs_price(100, 100, 1.0, 0.05, 0.2, kind="straddle")
