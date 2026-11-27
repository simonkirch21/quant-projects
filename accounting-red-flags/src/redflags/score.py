"""Score composite : chaque signal vaut 1 s'il est allumé, 0 sinon. Le score est la
part des signaux allumés parmi ceux qui peuvent être calculés cette année-là.

Les seuils sont documentés ici, fixés à l'avance et identiques pour toutes les
sociétés. Ceux qui ne viennent pas de la littérature (DSO, dette / trésorerie)
ont été choisis en connaissant l'issue de Wirecard : c'est un biais rétrospectif,
signalé dans le README.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .ratios import BENEISH_THRESHOLD

SIGNALS = {
    "m_score": ("M-Score de Beneish > -1,78", "Beneish (1999)"),
    "z_score": ("Z'' d'Altman hors zone saine (≤ 2,60)", "Altman (1995)"),
    "accruals": ("Accruals de Sloan > 5 % de l'actif", "Sloan (1996)"),
    "cash_conversion": ("Cash-flow d'exploitation < 80 % du résultat net", "usage courant"),
    "dso": ("Délai d'encaissement > 120 jours", "seuil fixé pour ce projet"),
    "receivables_vs_revenue": ("Créances : croissance > CA + 10 points", "usage courant"),
    "debt_while_cash": ("Dette / trésorerie > 30 % alors que la trésorerie > 20 % de l'actif", "seuil fixé pour ce projet"),
    "litigious_up": ("Vocabulaire juridique en hausse de plus de 25 %", "Loughran et McDonald (2011)"),
    "fog_up": ("Indice de Fog en hausse de plus de 1,5 point", "Li (2008)"),
    "llm_severe": ("Au moins un signal textuel vérifié de gravité ≥ 4 (mode Claude)", "ce projet"),
}


def signal_table(ind: pd.DataFrame, fin: pd.DataFrame, text: pd.DataFrame | None = None,
                 llm: pd.DataFrame | None = None) -> pd.DataFrame:
    df = ind.merge(fin[["company", "year", "cash", "total_assets"]], on=["company", "year"])
    if text is not None:
        t = text.sort_values(["company", "year"]).copy()
        t["litigious_change"] = t.groupby("company")["litigious"].pct_change()
        t["fog_change"] = t.groupby("company")["fog"].diff()
        df = df.merge(t[["company", "year", "litigious_change", "fog_change"]], on=["company", "year"], how="left")

    def flag(cond, available):
        return np.where(available, cond.astype(float), np.nan)

    s = pd.DataFrame({"company": df["company"], "year": df["year"]})
    s["m_score"] = flag(df["m_score"] > BENEISH_THRESHOLD, df["m_score"].notna())
    s["z_score"] = flag(df["z_double_prime"] <= 2.60, df["z_double_prime"].notna())
    s["accruals"] = flag(df["sloan_accruals"] > 0.05, df["sloan_accruals"].notna())
    s["cash_conversion"] = flag(df["cash_conversion"] < 0.8, df["cash_conversion"].notna())
    s["dso"] = flag(df["dso"] > 120, df["dso"].notna())
    gap = df["receivables_growth"] - df["revenue_growth"]
    s["receivables_vs_revenue"] = flag(gap > 0.10, gap.notna())
    s["debt_while_cash"] = flag((df["debt_to_cash"] > 0.30) & (df["cash"] / df["total_assets"] > 0.20),
                                df["debt_to_cash"].notna())
    if text is not None:
        s["litigious_up"] = flag(df["litigious_change"] > 0.25, df["litigious_change"].notna())
        s["fog_up"] = flag(df["fog_change"] > 1.5, df["fog_change"].notna())
    if llm is not None and len(llm):
        severe = llm[llm["gravite"] >= 4].groupby(["company", "year"]).size()
        covered = set(zip(llm["company"], llm["year"])) | set(llm.attrs.get("analyzed", []))
        s["llm_severe"] = [float(severe.get((c, y), 0) > 0) if (c, y) in covered else np.nan
                           for c, y in zip(s["company"], s["year"])]
    cols = [c for c in SIGNALS if c in s]
    s["signaux_allumes"] = s[cols].sum(axis=1)
    s["signaux_calculables"] = s[cols].notna().sum(axis=1)
    s["score"] = s["signaux_allumes"] / s["signaux_calculables"]
    return s
