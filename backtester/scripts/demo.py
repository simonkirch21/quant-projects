"""Génère la figure et les tableaux du README.

Lancement depuis le dossier backtester :  python scripts/demo.py
"""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backtester.data import load_prices  # noqa: E402
from backtester.engine import run_backtest  # noqa: E402
from backtester.metrics import drawdown, sharpe_ratio, summary  # noqa: E402
from backtester.strategies import buy_and_hold, sma_trend  # noqa: E402

COST = 0.001


def main():
    p = load_prices("SPY")
    runs = {
        "Acheter et garder": run_backtest(p, buy_and_hold(p), COST),
        "Moyenne 200 jours": run_backtest(p, sma_trend(p, 200), COST),
    }

    print("| | " + " | ".join(runs) + " |")
    print("|---|" + "---|" * len(runs))
    stats = {k: summary(v) for k, v in runs.items()}
    fmt = {
        "richesse finale": "{:.2f}", "rendement annuel": "{:.1%}", "volatilité": "{:.1%}",
        "sharpe": "{:.2f}", "pire chute": "{:.1%}", "temps investi": "{:.0%}", "transactions": "{}",
    }
    for key, f in fmt.items():
        print(f"| {key} | " + " | ".join(f.format(s[key]) for s in stats.values()) + " |")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    for name, bt in runs.items():
        ax1.plot(bt.index, bt["equity"], label=name)
        ax2.plot(bt.index, drawdown(bt["equity"]) * 100, label=name)
    ax1.set_yscale("log")
    ax1.set_yticks([0.5, 1, 2, 4, 8])
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g} €"))
    ax1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax1.set_ylabel("Richesse (1 € en 2005)")
    ax1.set_title("SPY 2005-2024, frais 0,10 % par transaction")
    ax1.legend()
    ax2.set_ylabel("Chute depuis le sommet (%)")
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "equity_drawdown.png", dpi=150)
    plt.close(fig)

    # Surapprentissage : 499 couples de moyennes mobiles (rapide, lente).
    # On choisit le meilleur sur 2006-2014, on regarde ce qu'il donne ensuite.
    rows = []
    for fast in range(5, 101, 5):
        for slow in range(20, 301, 10):
            if slow <= fast:
                continue
            sig = (p.rolling(fast).mean() > p.rolling(slow).mean()).astype(float)
            ret = run_backtest(p, sig, COST)["strategy_return"]
            rows.append((fast, slow, sharpe_ratio(ret.loc["2006":"2014"]),
                         sharpe_ratio(ret.loc["2015":])))
    ins, outs = np.array([r[2] for r in rows]), np.array([r[3] for r in rows])
    best = max(rows, key=lambda r: r[2])
    bh = p.pct_change().fillna(0)
    print(f"\n{len(rows)} combinaisons testées")
    print(f"meilleure sur 2006-2014 : ({best[0]}, {best[1]}) Sharpe {best[2]:.2f} "
          f"-> 2015-2024 : {best[3]:.2f}")
    print(f"médiane 2015-2024 de toutes les combinaisons : {np.median(outs):.2f}")
    print(f"corrélation classement avant / après : {np.corrcoef(ins, outs)[0, 1]:.2f}")
    print(f"acheter et garder 2015-2024 : {sharpe_ratio(bh.loc['2015':]):.2f}")


if __name__ == "__main__":
    main()
