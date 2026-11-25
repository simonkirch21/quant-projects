"""Génère la figure et les tableaux du README.

Lancement depuis le dossier risk-model :  python scripts/demo.py
"""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from riskmodel.backtest import basel_zone, christoffersen_independence, exceptions, kupiec_pof  # noqa: E402
from riskmodel.data import load_returns  # noqa: E402
from riskmodel.portfolio import portfolio_returns, risk_contributions  # noqa: E402
from riskmodel.var import historical_es, historical_var, normal_es, normal_var, rolling_var  # noqa: E402

WEIGHTS = {"SPY": 0.6, "TLT": 0.3, "GLD": 0.1}
LABELS = {"historical": "Historique 250 j", "normal": "Normale 250 j",
          "ewma": "Normale EWMA", "fhs": "Historique filtrée"}


def main():
    R = load_returns(list(WEIGHTS))
    rp = portfolio_returns(R, WEIGHTS)

    print("VaR et ES à 1 jour, 99 %, sur 20 ans :")
    print(f"  historique : VaR {historical_var(rp):.2%}  ES {historical_es(rp):.2%}")
    print(f"  normale    : VaR {normal_var(rp.mean(), rp.std()):.2%}  "
          f"ES {normal_es(rp.mean(), rp.std()):.2%}")
    print(f"  pire jour  : {-rp.min():.2%} ({rp.idxmin().date()})")

    print("\nContributions au risque :")
    print(risk_contributions(R, WEIGHTS).round(4).to_string())
    print("\nCorrélations :")
    print(R.corr().round(2).to_string())

    forecasts = pd.concat({m: rolling_var(rp, m) for m in LABELS}, axis=1).dropna()
    r = rp.loc[forecasts.index]
    print(f"\nBacktest du {r.index[0].date()} au {r.index[-1].date()} ({len(r)} jours)")
    print("| Méthode | Dépassements | Attendus | Taux | Kupiec p | Indépendance p "
          "| Pire fenêtre 250 j | Temps en zone rouge |")
    print("|---|---|---|---|---|---|---|---|")
    for m, label in LABELS.items():
        e = exceptions(r, forecasts[m])
        k, c = kupiec_pof(len(e), int(e.sum())), christoffersen_independence(e)
        roll = e.rolling(250).sum().dropna()
        print(f"| {label} | {k['exceptions']} | {k['attendues']:.0f} | {k['taux']:.2%} | "
              f"{k['p_value']:.3f} | {c['p_value']:.3f} | {int(roll.max())} "
              f"({basel_zone(int(roll.max()))}) | {(roll >= 10).mean():.0%} |")
    for year in ("2008", "2020", "2022"):
        counts = {LABELS[m]: int(exceptions(r, forecasts[m]).loc[year].sum()) for m in LABELS}
        print(year, counts)

    fig, axes = plt.subplots(2, 1, figsize=(9, 6.5))
    for ax, (start, end, title) in zip(axes, [
        (r.index[0], r.index[-1], "Portefeuille 60 % SPY / 30 % TLT / 10 % GLD"),
        ("2020-01-01", "2020-06-30", "Zoom : krach Covid 2020"),
    ]):
        rr, ff = r.loc[start:end], forecasts.loc[start:end]
        if len(rr) > 500:
            ax.plot(rr.index, rr * 100, lw=0.4, color="grey", label="Rendement du jour")
        else:
            ax.bar(rr.index, rr * 100, width=1.0, color="grey", alpha=0.6, label="Rendement du jour")
        ax.plot(ff.index, -ff["normal"] * 100, lw=1.2, label="−VaR normale 250 j")
        ax.plot(ff.index, -ff["fhs"] * 100, lw=1.2, label="−VaR historique filtrée")
        exc = rr[-rr > ff["fhs"]]
        ax.scatter(exc.index, exc * 100, color="red", s=12, zorder=3,
                   label="Dépassement (filtrée)")
        ax.set_ylabel("%")
        ax.set_title(title)
    axes[0].legend(loc="upper left", fontsize=8, ncol=2)
    axes[0].set_ylim(-11, 9)
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "var_backtest.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
