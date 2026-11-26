"""Chiffres du rapport de validation (VALIDATION.md) du modèle « historique filtrée ».

Lancement depuis le dossier risk-model :  python scripts/validation.py
"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from riskmodel.backtest import basel_zone, christoffersen_independence, exceptions, kupiec_pof  # noqa: E402
from riskmodel.data import load_returns  # noqa: E402
from riskmodel.portfolio import portfolio_returns  # noqa: E402
from riskmodel.var import rolling_var  # noqa: E402

WEIGHTS = {"SPY": 0.6, "TLT": 0.3, "GLD": 0.1}
START = "2009-01-01"   # période commune à toutes les variantes (fenêtre de 1 000 jours)


def independent_fhs(r: np.ndarray, t: int, lam=0.94, window=500, alpha=0.01) -> float:
    """Réimplémentation indépendante, en boucle simple, de la VaR du jour t."""
    var = r[0] ** 2
    sig = [np.nan]                        # sig[i] = volatilité prévue pour le jour i
    for i in range(1, t + 1):
        var = r[0] ** 2 if i == 1 else lam * var + (1 - lam) * r[i - 1] ** 2
        sig.append(np.sqrt(var))
    z = np.array([r[i] / sig[i] for i in range(t - window, t)])
    return -np.quantile(z, alpha) * sig[t]


def stats(r, v):
    e = exceptions(r, v)
    k, c = kupiec_pof(len(e), int(e.sum())), christoffersen_independence(e)
    roll = e.rolling(250).sum().dropna()
    return k, c, int(roll.max())


def main():
    rp = portfolio_returns(load_returns(list(WEIGHTS)), WEIGHTS)
    model = rolling_var(rp, "fhs")

    print("## Réimplémentation indépendante (10 dernières dates)")
    arr = rp.to_numpy()
    diffs = [abs(independent_fhs(arr, t) - model.iloc[t]) for t in range(len(arr) - 10, len(arr))]
    print(f"écart maximal : {max(diffs):.2e}")

    print("\n## Sensibilité au calibrage (période commune 2009-2024)")
    print("| lambda | fenêtre | Dépassements | Attendus | Kupiec p | Indépendance p | Pire fenêtre 250 j |")
    print("|---|---|---|---|---|---|---|")
    for lam in (0.94, 0.97):
        for window in (250, 500, 1000):
            v = rolling_var(rp, "fhs", lam=lam, fhs_window=window)
            r = rp.loc[START:]
            k, c, worst = stats(r, v.loc[START:])
            print(f"| {lam} | {window} | {k['exceptions']} | {k['attendues']:.0f} | "
                  f"{k['p_value']:.3f} | {c['p_value']:.3f} | {worst} ({basel_zone(worst)}) |")

    print("\n## Stabilité par sous-période : 2007-2015 contre 2016-2024")
    for a, b in (("2007", "2015"), ("2016", "2024")):
        r = rp.loc[a:b]
        k, c, worst = stats(r, model.loc[a:b])
        print(f"{a}-{b} : {k['exceptions']} dépassements pour {k['attendues']:.0f} attendus, "
              f"Kupiec p {k['p_value']:.3f}, indépendance p {c['p_value']:.3f}, pire fenêtre {worst}")

    print("\n## Dépassements par année")
    e = exceptions(rp, model)
    print(e.groupby(e.index.year).sum().astype(int).to_dict())

    print("\n## Grappes : dépassements suivis d'un autre dans les 5 jours")
    idx = np.flatnonzero(e.to_numpy())
    close = int(sum(1 for i, j in zip(idx[:-1], idx[1:]) if j - i <= 5))
    print(f"{close} sur {len(idx)}")

    print("\n## Ampleur des dépassements (perte / VaR)")
    df = pd.concat({"r": rp, "v": model}, axis=1).dropna()
    over = (-df["r"] / df["v"])[-df["r"] > df["v"]]
    print(f"moyenne {over.mean():.2f}, maximum {over.max():.2f} ({over.idxmax().date()})")
    print(f"sous la loi normale, ratio moyen attendu : {norm.pdf(norm.ppf(0.01)) / 0.01 / -norm.ppf(0.01):.2f}")


if __name__ == "__main__":
    main()
