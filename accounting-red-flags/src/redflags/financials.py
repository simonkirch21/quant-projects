"""Chargement et contrôle des données financières (data/financials.csv).

Tous les montants sont en millions d'euros. Le guide des postes est dans
data/GUIDE_POSTES.md ; data/template.csv est un modèle vide.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data"
REQUIRED = ["revenue", "cost_of_sales", "sga", "depreciation", "ebit", "net_income", "cfo",
            "receivables", "current_assets", "ppe", "total_assets", "current_liabilities",
            "long_term_debt", "total_liabilities", "equity", "retained_earnings"]


def load(path: str | Path = DATA / "financials.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df["securities"] = df["securities"].fillna(0.0)
    return df.sort_values(["company", "year"]).reset_index(drop=True)


def check(df: pd.DataFrame, tol: float = 0.15) -> list[str]:
    """Contrôles de cohérence comptable. Renvoie la liste des anomalies (vide si tout va bien).
    tol : écart toléré en millions (arrondis des rapports publiés en millions)."""
    problems = []
    for _, r in df.iterrows():
        tag = f"{r['company']} {r['year']}"
        missing = [c for c in REQUIRED if pd.isna(r[c])]
        if missing:
            problems.append(f"{tag} : postes manquants {missing}")
            continue
        if abs(r["total_liabilities"] + r["equity"] - r["total_assets"]) > tol:
            problems.append(f"{tag} : actif {r['total_assets']} ≠ passif {r['total_liabilities']} + capitaux propres {r['equity']}")
        for small, big in (("current_assets", "total_assets"), ("receivables", "current_assets"),
                           ("cash", "current_assets"), ("current_liabilities", "total_liabilities"),
                           ("cost_of_sales", "revenue")):
            if r[small] > r[big] + tol:
                problems.append(f"{tag} : {small} ({r[small]}) > {big} ({r[big]})")
        if r["ebit"] > r["revenue"]:
            problems.append(f"{tag} : EBIT supérieur au chiffre d'affaires")
    return problems
