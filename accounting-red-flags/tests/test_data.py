"""Tests sur les vraies données (data/financials.csv) et sur le score composite."""

import numpy as np
import pandas as pd
import pytest

from redflags.financials import check, load
from redflags.indicators import compute
from redflags.ratios import BENEISH_THRESHOLD
from redflags.score import signal_table


@pytest.fixture(scope="module")
def fin():
    return load()


def test_data_is_consistent(fin):
    assert check(fin) == []                       # actif = passif + capitaux propres, sous-totaux…
    assert set(fin["company"]) == {"Wirecard", "Adyen"}
    assert fin["source"].notna().all() and fin["pages"].notna().all()   # chaque ligne est sourcée


def test_check_detects_an_unbalanced_balance_sheet(fin):
    bad = fin.copy()
    bad.loc[0, "total_assets"] += 100
    assert any("≠" in p for p in check(bad))


def test_known_values(fin):
    w18 = fin[(fin.company == "Wirecard") & (fin.year == 2018)].iloc[0]
    assert w18["revenue"] == pytest.approx(2016.2)
    assert w18["receivables"] == pytest.approx(684.9 + 357.4)


def test_wirecard_never_crosses_the_beneish_threshold(fin):
    """Résultat central du projet : le M-Score ne détecte pas Wirecard."""
    ind = compute(fin)
    w = ind[(ind.company == "Wirecard") & ind.m_score.notna()]
    assert len(w) == 5 and (w["m_score"] < BENEISH_THRESHOLD).all()


def test_adyen_2018_is_a_false_positive_driven_by_aqi(fin):
    ind = compute(fin).set_index(["company", "year"])
    assert ind.loc[("Adyen", 2018), "m_score"] > BENEISH_THRESHOLD
    assert ind.loc[("Adyen", 2018), "beneish_AQI"] > 10


def test_adjusted_cash_flow_changes_the_inputs(fin):
    a, b = compute(fin), compute(fin, cfo_column="cfo_adjusted")
    w = lambda t: t[(t.company == "Wirecard") & (t.year == 2017)]["cash_conversion"].iloc[0]
    assert w(a) == pytest.approx(563.486 / 259.719)
    assert w(b) == pytest.approx(375.693 / 259.719)


def test_signal_table_counts_and_missing_values(fin):
    ind = compute(fin)
    text = pd.DataFrame({"company": ["Wirecard"] * 2, "year": [2017, 2018],
                         "litigious": [4.9, 7.2], "fog": [21.9, 22.0]})
    sig = signal_table(ind, fin, text).set_index(["company", "year"])
    w18 = sig.loc[("Wirecard", 2018)]
    assert w18["dso"] == 1 and w18["debt_while_cash"] == 1 and w18["receivables_vs_revenue"] == 1
    assert w18["litigious_up"] == 1 and w18["fog_up"] == 0
    assert np.isnan(sig.loc[("Wirecard", 2013), "m_score"])          # pas d'année précédente
    assert w18["score"] == pytest.approx(w18["signaux_allumes"] / w18["signaux_calculables"])
