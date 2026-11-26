"""Génère les figures et les tableaux du README.

Lancement depuis le dossier credit-risk :  python scripts/demo.py
"""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_curve
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from creditrisk.basel import (  # noqa: E402
    R_QRRE, expected_loss, irb_capital_k, simulate_portfolio_losses, vasicek_conditional_pd,
)
from creditrisk.data import TARGET, build_features, exposure_at_default, load_raw  # noqa: E402
from creditrisk.metrics import auc, brier, gini, hosmer_lemeshow, ks, psi  # noqa: E402
from creditrisk.rating import MasterScale  # noqa: E402
from creditrisk.scorecard import Scorecard  # noqa: E402

LGD = 0.80     # hypothèse : perte en cas de défaut d'un crédit renouvelable non garanti
SEED = 42


def main():
    df = load_raw()
    X, y = build_features(df), df[TARGET]
    tr, te = train_test_split(df.index, test_size=0.3, stratify=y, random_state=SEED)
    print(f"{len(df)} clients, taux de défaut {y.mean():.1%} ; apprentissage {len(tr)}, test {len(te)}")

    # 1. Grille de score
    sc = Scorecard().fit(X.loc[tr], y.loc[tr])
    iv = sc.encoder.information_values()
    print("\n## Information Value et coefficients")
    for f, v in iv.items():
        coef = sc.coefficients().get(f)
        status = f"{coef:+.3f}" if coef is not None else "retirée (signe incohérent)"
        print(f"| {f} | {v:.3f} | {status} |")

    print("\n## Grille de points (extrait : retard du dernier mois)")
    pts = sc.points_table()
    print(pts[pts["variable"] == "retard_dernier_mois"][["classe", "woe", "points"]].round(2).to_string(index=False))

    # 2. Performance : grille contre modèle « boîte noire »
    gb = HistGradientBoostingClassifier(random_state=0, max_iter=300, learning_rate=0.05)
    gb.fit(X.loc[tr], y.loc[tr])
    p_sc_tr, p_sc = sc.predict_pd(X.loc[tr]), sc.predict_pd(X.loc[te])
    p_gb = gb.predict_proba(X.loc[te])[:, 1]
    print("\n## Performance sur l'échantillon de test")
    print("| Modèle | AUC | Gini | KS | Brier |\n|---|---|---|---|---|")
    for name, p in (("Grille de score (régression logistique)", p_sc), ("Gradient boosting", p_gb)):
        print(f"| {name} | {auc(y.loc[te], p):.3f} | {gini(y.loc[te], p):.3f} | {ks(y.loc[te], p):.3f} | {brier(y.loc[te], p):.4f} |")
    print(f"Grille, apprentissage : AUC {auc(y.loc[tr], p_sc_tr):.3f} (écart avec le test : surapprentissage limité)")
    print(f"PSI des scores apprentissage / test : {psi(sc.score(X.loc[tr]), sc.score(X.loc[te])):.4f}")
    print(f"Hosmer-Lemeshow sur la PD brute du modèle (test) : p = {hosmer_lemeshow(y.loc[te], p_sc)['p_value']:.1e}")

    # 3. Échelle de notation
    ms = MasterScale().fit(p_sc_tr, y.loc[tr])
    bt = ms.backtest(p_sc, y.loc[te])
    print("\n## Échelle de notation (PD calibrée sur l'apprentissage, vérifiée sur le test)")
    print("| Classe | Clients | PD calibrée | Taux observé | p-value | Verdict |\n|---|---|---|---|---|---|")
    for g, r in bt.iterrows():
        print(f"| {g} | {r['clients']} | {r['PD calibrée']:.1%} | {r['taux observé']:.1%} | {r['p_value']:.2f} | {r['verdict']} |")
    gt = ms.global_test(p_sc, y.loc[te])
    print(f"test global : statistique {gt['statistique']:.1f}, p = {gt['p_value']:.2f}")

    # 4. Perte attendue et capital
    pd_te = ms.calibrated_pd(p_sc)
    ead = exposure_at_default(df.loc[te]).to_numpy()
    el = expected_loss(pd_te, LGD, ead)
    cap = irb_capital_k(pd_te, LGD) * ead
    realised = float((y.loc[te].to_numpy() * LGD * ead).sum())
    grades = ms.grade(p_sc)
    t = pd.DataFrame({"g": grades, "ead": ead, "el": el, "cap": cap}).groupby("g").sum()
    print("\n## Perte attendue et capital Bâle IRB par classe (montants en millions de NT$)")
    print("| Classe | PD | EAD | Perte attendue | Capital | Capital / EAD | Pondération (RW) |")
    print("|---|---|---|---|---|---|---|")
    for g, r in t.iterrows():
        print(f"| {g} | {ms.grade_pd[g]:.1%} | {r['ead'] / 1e6:.0f} | {r['el'] / 1e6:.1f} | "
              f"{r['cap'] / 1e6:.1f} | {r['cap'] / r['ead']:.1%} | {12.5 * r['cap'] / r['ead']:.0%} |")
    print(f"| Total | {np.average(pd_te, weights=ead):.1%} | {ead.sum() / 1e6:.0f} | {el.sum() / 1e6:.1f} | "
          f"{cap.sum() / 1e6:.1f} | {cap.sum() / ead.sum():.1%} | {12.5 * cap.sum() / ead.sum():.0%} |")
    print(f"perte réellement observée sur le test : {realised / 1e6:.1f} M ({realised / ead.sum():.1%} de l'EAD), "
          f"prévue : {el.sum() / 1e6:.1f} M ({el.sum() / ead.sum():.1%})")

    # 5. Portefeuille : Monte Carlo
    losses = simulate_portfolio_losses(pd_te, LGD, ead, R_QRRE, n_sims=20_000, seed=0)
    el_mc, var999 = losses.mean(), np.quantile(losses, 0.999)
    asrf = float((LGD * ead * vasicek_conditional_pd(pd_te, R_QRRE)).sum())
    print("\n## Distribution des pertes du portefeuille (20 000 scénarios, corrélation 4 %)")
    print(f"perte moyenne {el_mc / 1e6:.1f} M ; VaR 99,9 % {var999 / 1e6:.1f} M ; "
          f"perte inattendue {(var999 - el_mc) / 1e6:.1f} M ; capital IRB {cap.sum() / 1e6:.1f} M "
          f"(écart {(var999 - el_mc) / cap.sum() - 1:+.1%}) ; quantile ASRF {asrf / 1e6:.1f} M")
    sens = {}
    for rho in (0.04, 0.10, 0.15):
        L = simulate_portfolio_losses(pd_te, LGD, ead, rho, n_sims=20_000, seed=1)
        sens[rho] = L
        print(f"corrélation {rho:.0%} : VaR 99 % {np.quantile(L, 0.99) / 1e6:.1f} M ; "
              f"VaR 99,9 % {np.quantile(L, 0.999) / 1e6:.1f} M ; écart-type {L.std() / 1e6:.1f} M")

    # Figures
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    ax = axes[0]
    for name, p in (("Grille de score", p_sc), ("Gradient boosting", p_gb)):
        fpr, tpr, _ = roc_curve(y.loc[te], p)
        ax.plot(fpr, tpr, label=f"{name} (AUC {auc(y.loc[te], p):.3f})")
    ax.plot([0, 1], [0, 1], ls=":", color="grey", label="Hasard")
    ax.set_xlabel("Bons clients refusés à tort")
    ax.set_ylabel("Mauvais clients détectés")
    ax.set_title("Courbe ROC (échantillon de test)")
    ax.legend(fontsize=8)

    ax = axes[1]
    x = np.arange(len(bt))
    ax.bar(x - 0.2, bt["PD calibrée"] * 100, 0.4, label="PD calibrée (apprentissage)")
    ax.bar(x + 0.2, bt["taux observé"] * 100, 0.4, label="Taux observé (test)")
    ax.set_xticks(x, bt.index)
    ax.set_ylabel("Taux de défaut (%)")
    ax.set_title("Échelle de notation")
    ax.legend(fontsize=8)

    ax = axes[2]
    for rho, L in sens.items():
        ax.hist(L / 1e6, bins=120, density=True, histtype="step", lw=1.3, label=f"corrélation {rho:.0%}")
    ax.axvline(el_mc / 1e6, color="black", ls="--", lw=1, label="Perte attendue")
    ax.axvline(var999 / 1e6, color="tab:red", ls="--", lw=1, label="VaR 99,9 % (4 %)")
    ax.set_xlabel("Perte du portefeuille (millions de NT$)")
    ax.set_title("Distribution des pertes (Monte Carlo)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "credit_risk.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
