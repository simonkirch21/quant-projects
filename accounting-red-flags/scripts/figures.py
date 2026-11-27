"""Figure de synthèse du README (figures/synthese.png).
Lancement depuis le dossier accounting-red-flags, après python -m redflags analyze."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COL = {"Wirecard": "#c0392b", "Adyen": "#2471a3"}


def main():
    ind = pd.read_csv(ROOT / "outputs" / "indicators.csv")
    text = pd.read_csv(ROOT / "outputs" / "text_scores.csv")
    fig, axes = plt.subplots(2, 2, figsize=(12, 7.5))
    panels = [
        (ind, "m_score", "M-Score de Beneish (alerte au-dessus de -1,78)", -1.78),
        (ind, "dso", "Délai d'encaissement des créances (jours)", 120),
        (ind, "debt_to_cash", "Dettes financières / trésorerie", 0.30),
        (text, "litigious", "Vocabulaire juridique du rapport de gestion (pour 1 000 mots)", None),
    ]
    for ax, (df, col, title, thr) in zip(axes.flat, panels):
        for c, g in df.groupby("company"):
            g = g.dropna(subset=[col])
            ax.plot(g["year"], g[col], marker="o", lw=2.5, color=COL[c], label=c)
        if thr is not None:
            ax.axhline(thr, ls="--", color="black", lw=1)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(range(2013, 2020))
        ax.grid(alpha=0.3)
    axes[0, 0].legend(loc="center left")
    axes[0, 0].annotate("Adyen 2018 : fausse alerte\n(nouvel actif IFRS 15)", xy=(2018, 4.0), xytext=(2014.3, 2.6),
                        arrowprops=dict(arrowstyle="->"), fontsize=9)
    axes[0, 0].annotate("Wirecard : jamais au-dessus du seuil", xy=(2016, -2.32), xytext=(2013.2, 0.2), fontsize=9,
                        arrowprops=dict(arrowstyle="->"))
    axes[1, 1].annotate("2018 : enquête à Singapour\nmentionnée (p. 97)", xy=(2018, 7.2), xytext=(2014.2, 8.6),
                        arrowprops=dict(arrowstyle="->"), fontsize=9)
    fig.suptitle("Wirecard contre Adyen : ce que les indicateurs voyaient avant le scandale de 2020", fontsize=13)
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "synthese.png", dpi=150)


if __name__ == "__main__":
    main()
