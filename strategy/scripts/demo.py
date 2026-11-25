"""Génère la figure et les tableaux du README.

Lancement depuis le dossier strategy :  python scripts/demo.py
"""

from pathlib import Path
import math
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent / "backtester")]

from backtester.data import load_prices  # noqa: E402
from backtester.metrics import annual_volatility, cagr, max_drawdown, sharpe_ratio  # noqa: E402
from strategy.portfolio import equity, run_portfolio  # noqa: E402
from strategy.robustness import (  # noqa: E402
    block_bootstrap_sharpe, block_bootstrap_sharpe_diff, deflated_sharpe_ratio,
    expected_max_sharpe, probabilistic_sharpe_ratio,
)
from strategy.signals import target_weights, vol_scale  # noqa: E402
from strategy.walkforward import walk_forward  # noqa: E402

TICKERS = ["SPY", "TLT", "GLD"]
START = "2006"            # 2005 sert d'historique aux moyennes et volatilités
TREND_GRID = [50, 100, 150, 200, 250]
LOOKBACKS = [20, 40, 60, 120, 250]
TARGETS = [0.05, 0.10, 0.15, 0.20]


def stats(r: pd.Series) -> str:
    e = equity(r)
    return (f"{sharpe_ratio(r):.2f} | {cagr(e):.1%} | {annual_volatility(r):.1%} | "
            f"{max_drawdown(e):.1%}")


def vol_only(P, lookback=60, target=0.10):
    w = pd.DataFrame({c: vol_scale(P[c], target, lookback) / P.shape[1] for c in P})
    return run_portfolio(P, w)


def main():
    P = pd.concat({t: load_prices(t) for t in TICKERS}, axis=1).dropna()
    run = {
        "Diversifié + ciblage de vol": vol_only(P),
        "Tendance 200 j + ciblage de vol": run_portfolio(P, target_weights(P, 200)),
        "Tendance 200 j seule": run_portfolio(P, target_weights(P, 200, use_vol=False)),
        "1/3 chacun (rééquilibré)": run_portfolio(P, pd.DataFrame(1 / 3, index=P.index, columns=P.columns)),
        "60/40 SPY/TLT": run_portfolio(P[["SPY", "TLT"]], pd.DataFrame({"SPY": 0.6, "TLT": 0.4}, index=P.index)),
        "SPY seul": P["SPY"].pct_change().fillna(0.0),
    }
    run = {k: v.loc[START:] for k, v in run.items()}

    print("## 2006-2024 : Sharpe | rendement annuel | volatilité | pire chute | 2008 | 2022")
    for k, r in run.items():
        y = {yr: (1 + r.loc[yr]).prod() - 1 for yr in ("2008", "2022")}
        print(f"| {k} | {stats(r)} | {y['2008']:+.1%} | {y['2022']:+.1%} |")

    # 1. Walk-forward sur la fenêtre de tendance
    by_window = {n: run_portfolio(P, target_weights(P, n)) for n in TREND_GRID}
    oos, chosen = walk_forward(by_window, 2010, 2024, train_years=5)
    best_hindsight = max(TREND_GRID, key=lambda n: sharpe_ratio(by_window[n].loc["2010":]))
    print("\n## Walk-forward 2010-2024 (Sharpe | rendement | vol | pire chute)")
    print(f"| Walk-forward | {stats(oos)} |")
    print(f"| Meilleure fenêtre a posteriori ({best_hindsight} j) | "
          f"{stats(by_window[best_hindsight].loc['2010':])} |")
    print(f"| Diversifié + ciblage de vol | {stats(run['Diversifié + ciblage de vol'].loc['2010':])} |")
    print("fenêtres choisies :", chosen.to_dict())

    # 2. Sensibilité aux paramètres
    sens_trend = {n: sharpe_ratio(by_window[n].loc[START:]) for n in TREND_GRID}
    sens_lb = {lb: sharpe_ratio(vol_only(P, lookback=lb).loc[START:]) for lb in LOOKBACKS}
    sens_tv = {tv: sharpe_ratio(vol_only(P, target=tv).loc[START:]) for tv in TARGETS}
    print("\n## Sensibilité (Sharpe 2006-2024)")
    print("tendance, fenêtre :", {k: round(v, 2) for k, v in sens_trend.items()})
    print("ciblage, historique de vol :", {k: round(v, 2) for k, v in sens_lb.items()})
    print("ciblage, vol cible :", {k: round(v, 2) for k, v in sens_tv.items()})

    # 3. Frais
    w_vol = pd.DataFrame({c: vol_scale(P[c], 0.10, 60) / 3 for c in P})
    print("\n## Frais :", {c: round(sharpe_ratio(run_portfolio(P, w_vol, cost=c).loc[START:]), 2)
                          for c in (0.0, 0.001, 0.003)})

    # 4. Sous-périodes
    best = run["Diversifié + ciblage de vol"]
    print("\n## Sous-périodes (Sharpe)")
    for a, b in (("2006", "2010"), ("2011", "2015"), ("2016", "2020"), ("2021", "2024")):
        print(f"| {a}-{b} | " + " | ".join(
            f"{sharpe_ratio(run[k].loc[a:b]):.2f}"
            for k in ("Diversifié + ciblage de vol", "Tendance 200 j + ciblage de vol",
                      "1/3 chacun (rééquilibré)")) + " |")

    # 5. Statistiques : bootstrap, PSR, DSR
    ci = np.percentile(block_bootstrap_sharpe(best), [2.5, 97.5])
    diff = block_bootstrap_sharpe_diff(best, run["1/3 chacun (rééquilibré)"])
    diff_t = block_bootstrap_sharpe_diff(run["Tendance 200 j + ciblage de vol"], best)
    variants = ([by_window[n].loc[START:] for n in TREND_GRID]
                + [run["Tendance 200 j seule"]]
                + [vol_only(P, lookback=lb).loc[START:] for lb in LOOKBACKS]
                + [vol_only(P, target=tv).loc[START:] for tv in TARGETS if tv != 0.10])
    srs = [v.mean() / v.std() for v in variants]
    print("\n## Statistiques")
    print(f"IC 95 % du Sharpe (bootstrap par blocs) : [{ci[0]:.2f} ; {ci[1]:.2f}]")
    print(f"Écart de Sharpe contre 1/3 chacun : {np.mean(diff):+.2f}, IC 95 % "
          f"[{np.percentile(diff, 2.5):+.2f} ; {np.percentile(diff, 97.5):+.2f}], "
          f"P(pas mieux) = {(diff <= 0).mean():.0%}")
    print(f"Tendance contre diversifié : P(tendance meilleure) = {(diff_t >= 0).mean():.0%}")
    print(f"Variantes essayées : {len(srs)} ; Sharpe max attendu par hasard : "
          f"{expected_max_sharpe(np.var(srs, ddof=1), len(srs)) * math.sqrt(252):.2f}")
    print(f"PSR (vrai Sharpe > 0) : {probabilistic_sharpe_ratio(best):.1%} ; "
          f"DSR : {deflated_sharpe_ratio(best, srs):.1%}")

    # Figure
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), gridspec_kw={"width_ratios": [2, 1]})
    for k in ("Diversifié + ciblage de vol", "Tendance 200 j + ciblage de vol",
              "1/3 chacun (rééquilibré)", "60/40 SPY/TLT", "SPY seul"):
        ax1.plot(equity(run[k]), label=k, lw=1.2)
    ax1.set_yscale("log")
    ax1.set_yticks([0.5, 1, 2, 4, 8])
    ax1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g} €"))
    ax1.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax1.set_title("1 € investi début 2006, frais 0,10 %")
    ax1.legend(fontsize=8)

    labels = [f"tend. {n}" for n in TREND_GRID] + [f"vol {lb} j" for lb in LOOKBACKS]
    values = list(sens_trend.values()) + list(sens_lb.values())
    colors = ["tab:orange"] * len(TREND_GRID) + ["tab:blue"] * len(LOOKBACKS)
    ax2.barh(labels, values, color=colors)
    ax2.invert_yaxis()
    ax2.set_xlabel("Sharpe 2006-2024")
    ax2.set_title("Sensibilité aux paramètres")
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "strategy.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
