import math

import numpy as np
import pandas as pd
import pytest

from creditrisk.basel import (
    expected_loss, irb_capital_k, risk_weighted_assets, simulate_portfolio_losses,
    vasicek_conditional_pd,
)
from creditrisk.data import EXCLUDED, build_features, exposure_at_default, load_raw
from creditrisk.metrics import auc, gini, hosmer_lemeshow, ks, psi
from creditrisk.rating import GRADES, MasterScale
from creditrisk.scorecard import Scorecard
from creditrisk.woe import WoEEncoder, woe_table


def synthetic(n=20_000, seed=0):
    """Données simulées dont on connaît la vraie relation : log-cote = -1,5 + 1,2 x1 - 0,8 x2."""
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({"x1": rng.normal(size=n), "x2": rng.normal(size=n),
                      "bruit": rng.normal(size=n), "cat": rng.choice(["a", "b", "c"], n)})
    logit = -1.5 + 1.2 * X["x1"] - 0.8 * X["x2"] + X["cat"].map({"a": 0.0, "b": 0.5, "c": -0.5})
    p = 1 / (1 + np.exp(-logit))
    y = pd.Series((rng.random(n) < p).astype(int))
    return X, y, p.to_numpy()


# --- Données ---------------------------------------------------------------------

def test_protected_attributes_are_not_used():
    X = build_features(load_raw())
    assert not set(EXCLUDED) & set(X.columns)
    assert X.notna().all().all()


def test_ead_is_at_least_the_drawn_amount():
    df = load_raw()
    ead = exposure_at_default(df)
    assert (ead >= df["BILL_AMT1"].clip(lower=0) - 1e-9).all()
    assert (ead <= df[["LIMIT_BAL", "BILL_AMT1"]].max(axis=1) + 1e-9).all()


# --- WoE ---------------------------------------------------------------------------

def test_woe_and_iv_by_hand():
    bins = pd.Series(["A"] * 100 + ["B"] * 100)
    y = pd.Series([0] * 90 + [1] * 10 + [0] * 60 + [1] * 40)   # A : 10 % de défauts, B : 40 %
    t = woe_table(bins, y)
    good = (np.array([90, 60]) + 0.5) / 151
    bad = (np.array([10, 40]) + 0.5) / 51
    assert t["woe"].to_numpy() == pytest.approx(np.log(good / bad))
    assert t.loc["A", "woe"] > 0 > t.loc["B", "woe"]            # A plus sûre, B plus risquée
    assert t["iv"].sum() == pytest.approx(((good - bad) * np.log(good / bad)).sum())


def test_encoder_learns_on_train_and_handles_new_values():
    X, y, _ = synthetic()
    enc = WoEEncoder(n_bins=5, categorical=("cat",)).fit(X.iloc[:10_000], y.iloc[:10_000])
    new = pd.DataFrame({"x1": [100.0], "x2": [-100.0], "bruit": [0.0], "cat": ["inconnue"]})
    out = enc.transform(new)
    assert out.loc[0, "cat"] == 0.0                              # catégorie jamais vue : neutre
    assert out.loc[0, "x1"] == enc.tables["x1"]["woe"].iloc[-1]  # valeur extrême : dernière classe
    iv = enc.information_values()
    assert iv["x1"] > iv["x2"] > iv["bruit"] and iv["bruit"] < 0.02


# --- Grille de score -----------------------------------------------------------------

def test_scorecard_ranks_well_and_drops_noise():
    X, y, p_true = synthetic()
    sc = Scorecard(n_bins=8, categorical=("cat",)).fit(X.iloc[:14_000], y.iloc[:14_000])
    assert "bruit" not in sc.features                            # IV < 0,02
    assert (sc.coefficients() < 0).all()
    p = sc.predict_pd(X.iloc[14_000:])
    best = auc(y.iloc[14_000:], p_true[14_000:])                 # AUC du vrai modèle
    assert auc(y.iloc[14_000:], p) > best - 0.02


def test_points_add_up_to_the_score_and_pdo():
    X, y, _ = synthetic()
    sc = Scorecard(categorical=("cat",)).fit(X, y)
    table = sc.points_table().set_index(["variable", "classe"])["points"]
    row = X.iloc[[0]]
    total = sum(table[(f, sc.encoder._bin(f, row[f]).iloc[0])] for f in sc.features)
    assert total == pytest.approx(sc.score(row)[0], abs=1e-8)
    # Doubler la cote bons / mauvais ajoute exactement PDO = 20 points
    odds = lambda s: math.exp((s - sc.offset) / sc.factor)
    assert odds(620) / odds(600) == pytest.approx(2.0)


# --- Mesures -----------------------------------------------------------------------

def test_discrimination_metrics():
    y = np.array([0, 0, 0, 1, 1])
    assert auc(y, [0.1, 0.2, 0.3, 0.8, 0.9]) == 1.0
    assert gini(y, [0.1, 0.2, 0.3, 0.8, 0.9]) == 1.0
    assert ks(y, [0.1, 0.2, 0.3, 0.8, 0.9]) == pytest.approx(1.0)
    rng = np.random.default_rng(1)
    yy = rng.integers(0, 2, 50_000)
    assert abs(gini(yy, rng.random(50_000))) < 0.02            # score au hasard


def test_hosmer_lemeshow_accepts_true_pd_and_rejects_biased_pd():
    """Avec les vraies PD, le test ne doit rejeter qu'environ 5 % du temps (risque de
    première espèce) ; avec des PD biaisées de +50 %, presque toujours."""
    true_rej, biased_rej = [], []
    for seed in range(40):
        _, y, p = synthetic(n=10_000, seed=100 + seed)
        true_rej.append(hosmer_lemeshow(y, p)["p_value"] < 0.05)
        biased_rej.append(hosmer_lemeshow(y, np.clip(p * 1.5, 0, 0.99))["p_value"] < 0.05)
    assert np.mean(true_rej) <= 0.15
    assert np.mean(biased_rej) == 1.0


def test_psi():
    rng = np.random.default_rng(3)
    a = rng.normal(size=50_000)
    assert psi(a, rng.normal(size=50_000)) < 0.01
    assert psi(a, rng.normal(1.0, 1, 50_000)) > 0.25


# --- Échelle de notation -------------------------------------------------------------

def test_master_scale_is_monotone_and_calibrated():
    X, y, p = synthetic(n=40_000, seed=4)
    ms = MasterScale().fit(p[:20_000], y[:20_000])
    assert ms.grade_pd.is_monotonic_increasing
    bt = ms.backtest(p[20_000:], y[20_000:])
    assert list(bt.index) == GRADES
    # Calibration sur l'apprentissage, vérifiée sur un autre échantillon :
    # les écarts restent dans ce que permet le hasard (moins de 3 écarts-types par classe)
    z = (bt["taux observé"] - bt["PD calibrée"]) / np.sqrt(bt["PD calibrée"] * (1 - bt["PD calibrée"]) / bt["clients"])
    assert (z.abs() < 3).all()


# --- Bâle et portefeuille ------------------------------------------------------------

def test_irb_capital_properties():
    pds = np.array([0.001, 0.01, 0.05, 0.2, 0.5, 0.9, 1.0])
    k = irb_capital_k(pds, 0.8)
    assert (k[:-1] > 0).all() and k[-1] == pytest.approx(0.0)  # PD = 100 % : tout est perte attendue
    assert (vasicek_conditional_pd(pds[:-1], 0.04) > pds[:-1]).all()
    assert risk_weighted_assets(0.01, 0.8, 1_000.0) == pytest.approx(12.5 * irb_capital_k(0.01, 0.8) * 1_000)
    assert expected_loss(0.02, 0.5, 100.0) == pytest.approx(1.0)


def test_monte_carlo_matches_vasicek_for_a_large_portfolio():
    """Grand portefeuille homogène : la VaR 99,9 % simulée rejoint la formule de Vasicek."""
    n, pd_, lgd, rho = 5_000, 0.02, 0.6, 0.12
    losses = simulate_portfolio_losses(np.full(n, pd_), lgd, np.ones(n), rho, n_sims=20_000, seed=5)
    assert losses.mean() == pytest.approx(n * pd_ * lgd, rel=0.02)
    asrf = n * lgd * vasicek_conditional_pd(pd_, rho)
    assert np.quantile(losses, 0.999) == pytest.approx(asrf, rel=0.06)
