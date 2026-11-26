"""Stress tests, mesures réglementaires, GARCH et valeurs extrêmes.

Lancement depuis le dossier risk-model :  python scripts/stress_demo.py
"""

from pathlib import Path
import math
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from riskmodel.backtest import exceptions  # noqa: E402
from riskmodel.data import load_returns  # noqa: E402
from riskmodel.evt import evt_es, evt_var, fit_pot  # noqa: E402
from riskmodel.garch import fit_garch_t  # noqa: E402
from riskmodel.portfolio import portfolio_returns  # noqa: E402
from riskmodel.regulatory import (  # noqa: E402
    horizon_comparison, market_risk_capital, plus_factor, stressed_period,
)
from riskmodel.stress import historical_stress, hypothetical_stress, reverse_stress  # noqa: E402
from riskmodel.var import (  # noqa: E402
    historical_es, historical_var, normal_es, normal_var, rolling_var,
)

WEIGHTS = {"SPY": 0.6, "TLT": 0.3, "GLD": 0.1}


def pct(x):
    return f"{x:+.1%}"


def main():
    R = load_returns(list(WEIGHTS))
    rp = portfolio_returns(R, WEIGHTS)

    print("## Stress tests historiques (portefeuille non rééquilibré)")
    hist = historical_stress(R, WEIGHTS)
    print("| Scénario | SPY | TLT | GLD | Portefeuille |\n|---|---|---|---|---|")
    for name, row in hist.iterrows():
        print(f"| {name} | " + " | ".join(pct(row[c]) for c in [*WEIGHTS, "portefeuille"]) + " |")

    print("\n## Stress tests hypothétiques")
    hypo = hypothetical_stress(WEIGHTS)
    print("| Scénario | SPY | TLT | GLD | Portefeuille |\n|---|---|---|---|---|")
    for name, row in hypo.iterrows():
        print(f"| {name} | " + " | ".join(pct(row[c]) for c in [*WEIGHTS, "portefeuille"]) + " |")

    print("\n## Reverse stress test (horizon 1 mois, loi normale)")
    for loss in (0.10, 0.20):
        rs = reverse_stress(R.cov() * 21, WEIGHTS, loss)
        chocs = ", ".join(f"{k} {v:+.1%}" for k, v in rs["chocs"].items())
        p = rs["probabilité (loi normale)"]
        print(f"perte {loss:.0%} : {chocs} ; {rs['écarts-types']:.1f} écarts-types ; "
              f"probabilité {p:.1e} par mois, soit une fois tous les {1 / p / 12:,.0f} ans")

    print("\n## Horizon 10 jours : racine du temps contre rendements réels")
    for a in (0.01, 0.025):
        h = horizon_comparison(rp, 10, a)
        print(f"alpha {a:.1%} : " + ", ".join(f"{k} {v:.2%}" for k, v in h.items()))

    print("\n## VaR stressée et capital Bâle 2.5")
    start, end = stressed_period(rp)
    stressed = rp.loc[start:end]
    last = rp.iloc[-250:]
    fhs = rolling_var(rp, "fhs")
    n_exc = int(exceptions(rp, fhs).iloc[-250:].sum())
    var10 = historical_var(last) * math.sqrt(10)
    svar10 = historical_var(stressed) * math.sqrt(10)
    cap = market_risk_capital(var10, svar10, n_exc)
    print(f"période stressée : {start.date()} → {end.date()}")
    print(f"VaR 99 % 1 j (250 derniers jours) {historical_var(last):.2%} ; VaR stressée {historical_var(stressed):.2%}")
    print(f"ES 97,5 % 1 j (250 derniers jours) {historical_es(last, 0.025):.2%} ; ES stressée {historical_es(stressed, 0.025):.2%}")
    print(f"dépassements sur 250 j (historique filtrée) : {n_exc} -> majoration {plus_factor(n_exc)}")
    print(f"capital = {cap['multiplicateur']} x ({var10:.1%} + {svar10:.1%}) = {cap['capital']:.1%} du portefeuille")

    print("\n## GARCH(1,1) Student sur 20 ans")
    g = fit_garch_t(rp.to_numpy())
    print(f"a {g['a']:.3f}, b {g['b']:.3f}, persistance {g['persistance']:.3f}, "
          f"degrés de liberté {g['nu']:.1f}, volatilité de long terme {g['vol long terme annuelle']:.1%}")
    half_life = math.log(0.5) / math.log(g["persistance"])
    print(f"demi-vie d'un choc de volatilité : {half_life:.0f} jours")

    print("\n## Valeurs extrêmes (POT, seuil = 95e centile des pertes)")
    fit = fit_pot(-rp, 0.95)
    print(f"xi {fit['xi']:.2f}, beta {fit['beta']:.4f}, seuil {fit['u']:.2%}, {fit['n_u']} excès")
    print("| Niveau | VaR historique | VaR normale | VaR EVT | ES historique | ES normale | ES EVT |")
    print("|---|---|---|---|---|---|---|")
    mu, sd = rp.mean(), rp.std()
    for lv in (0.99, 0.995, 0.999):
        print(f"| {lv:.1%} | {historical_var(rp, 1 - lv):.2%} | {normal_var(mu, sd, 1 - lv):.2%} | "
              f"{evt_var(fit, lv):.2%} | {historical_es(rp, 1 - lv):.2%} | "
              f"{normal_es(mu, sd, 1 - lv):.2%} | {evt_es(fit, lv):.2%} |")

    fig, ax = plt.subplots(figsize=(9, 4))
    table = pd.concat([hist["portefeuille"], hypo["portefeuille"]]).sort_values()
    colors = ["tab:red" if k in hist.index else "tab:blue" for k in table.index]
    ax.barh([k.split(" (")[0] for k in table.index], table * 100, color=colors)
    ax.axvline(-historical_var(rp) * 100 * math.sqrt(10), color="black", ls="--", lw=1,
               label="VaR 99 % à 10 jours")
    ax.set_xlabel("Variation du portefeuille (%)")
    ax.set_title("Stress tests : rouge = historique, bleu = hypothétique")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "stress_tests.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
