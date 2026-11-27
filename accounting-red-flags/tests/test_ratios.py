"""Formules vérifiées sur des valeurs calculées à la main."""

import pytest

from redflags.ratios import (
    altman_z, altman_z_double_prime, beneish_components, beneish_m_score, cash_conversion,
    dso, sloan_accruals, z_zone,
)

PREV = dict(revenue=1000, cost_of_sales=600, receivables=100, current_assets=400, ppe=300,
            securities=0, total_assets=1000, depreciation=50, sga=200, current_liabilities=200,
            long_term_debt=200, net_income=80, cfo=100)
CUR = dict(revenue=1300, cost_of_sales=819, receivables=195, current_assets=500, ppe=300,
           securities=0, total_assets=1250, depreciation=45, sga=247, current_liabilities=300,
           long_term_debt=250, net_income=130, cfo=60)


def test_beneish_components_by_hand():
    c = beneish_components(CUR, PREV)
    # DSRI = (195/1300) / (100/1000) = 0,15 / 0,10
    assert c["DSRI"] == pytest.approx(1.5)
    # GMI = marge t-1 / marge t = 0,40 / (481/1300 = 0,37)
    assert c["GMI"] == pytest.approx(0.40 / 0.37)
    # AQI = (1 - 800/1250) / (1 - 700/1000) = 0,36 / 0,30
    assert c["AQI"] == pytest.approx(1.2)
    assert c["SGI"] == pytest.approx(1.3)
    # DEPI = (50/350) / (45/345)
    assert c["DEPI"] == pytest.approx((50 / 350) / (45 / 345))
    # SGAI = (247/1300 = 0,19) / (200/1000 = 0,20)
    assert c["SGAI"] == pytest.approx(0.95)
    # LVGI = (550/1250 = 0,44) / (400/1000 = 0,40)
    assert c["LVGI"] == pytest.approx(1.1)
    # TATA = (130 - 60) / 1250
    assert c["TATA"] == pytest.approx(0.056)


def test_beneish_m_score_by_hand():
    c = beneish_components(CUR, PREV)
    expected = (-4.84 + 0.920 * 1.5 + 0.528 * c["GMI"] + 0.404 * 1.2 + 0.892 * 1.3
                + 0.115 * c["DEPI"] - 0.172 * 0.95 + 4.679 * 0.056 - 0.327 * 1.1)
    assert beneish_m_score(CUR, PREV) == pytest.approx(expected)
    # -4,84 + 1,380 + 0,571 + 0,485 + 1,160 + 0,126 - 0,163 + 0,262 - 0,360
    assert beneish_m_score(CUR, PREV) == pytest.approx(-1.3799, abs=1e-4)   # > -1,78 : alerte


def test_beneish_neutral_company_is_below_threshold():
    """Une entreprise stable (tous les indices à 1, accruals nuls) donne
    -4,84 + 0,920 + 0,528 + 0,404 + 0,892 + 0,115 - 0,172 - 0,327 = -2,48."""
    assert beneish_m_score(PREV, PREV) == pytest.approx(-2.48 + 4.679 * (80 - 100) / 1000)
    assert beneish_m_score({**PREV, "net_income": 100}, {**PREV, "net_income": 100}) == pytest.approx(-2.48)


ALTMAN = dict(current_assets=400, current_liabilities=200, total_assets=1000, retained_earnings=300,
              ebit=150, market_cap=1200, total_liabilities=600, revenue=1500, equity=400)


def test_altman_z_by_hand():
    # 1,2 x 0,2 + 1,4 x 0,3 + 3,3 x 0,15 + 0,6 x 2 + 1,0 x 1,5 = 0,24 + 0,42 + 0,495 + 1,2 + 1,5
    assert altman_z(ALTMAN) == pytest.approx(3.855)
    assert z_zone(3.855) == "saine"


def test_altman_z_double_prime_by_hand():
    # 6,56 x 0,2 + 3,26 x 0,3 + 6,72 x 0,15 + 1,05 x 400/600
    assert altman_z_double_prime(ALTMAN) == pytest.approx(1.312 + 0.978 + 1.008 + 0.7)
    assert z_zone(1.0, double_prime=True) == "détresse"
    assert z_zone(2.0, double_prime=True) == "grise"


def test_accruals_cash_conversion_dso():
    assert sloan_accruals(CUR, PREV) == pytest.approx(70 / 1125)
    assert cash_conversion(CUR) == pytest.approx(60 / 130)
    assert dso(CUR) == pytest.approx(195 / 1300 * 365)


def test_debt_to_cash():
    from redflags.ratios import debt_to_cash
    assert debt_to_cash({"interest_bearing_debt": 1466.1, "cash": 2719.8}) == pytest.approx(0.539, abs=1e-3)
