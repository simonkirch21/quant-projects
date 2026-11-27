"""Tableau des indicateurs quantitatifs, société par société et année par année."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .ratios import (
    BENEISH_THRESHOLD, altman_z, altman_z_double_prime, beneish_components, beneish_m_score,
    cash_conversion, debt_to_cash, dso, sloan_accruals, z_zone,
)


def compute(df: pd.DataFrame, cfo_column: str = "cfo") -> pd.DataFrame:
    """Une ligne par société et par année. Les indicateurs qui comparent deux années
    (M-Score, accruals de Sloan, variation du DSO) commencent à la 2e année disponible.

    cfo_column : "cfo" (flux publié) ou "cfo_adjusted" (flux « ajusté » présenté par Wirecard).
    """
    rows = []
    for company, g in df.groupby("company"):
        g = g.sort_values("year").reset_index(drop=True)
        for i, cur in g.iterrows():
            cur = cur.to_dict()
            if cfo_column != "cfo" and not pd.isna(cur.get(cfo_column)):
                cur["cfo"] = cur[cfo_column]
            out = {"company": company, "year": cur["year"],
                   "dso": dso(cur), "cash_conversion": cash_conversion(cur),
                   "z_double_prime": altman_z_double_prime(cur),
                   "debt_to_cash": debt_to_cash(cur)}
            out["z_double_prime_zone"] = z_zone(out["z_double_prime"], double_prime=True)
            out["z_original"] = altman_z(cur) if not pd.isna(cur.get("market_cap")) else np.nan
            if i > 0:
                prev = g.loc[i - 1].to_dict()
                if cfo_column != "cfo" and not pd.isna(prev.get(cfo_column)):
                    prev["cfo"] = prev[cfo_column]
                out.update({f"beneish_{k}": v for k, v in beneish_components(cur, prev).items()})
                out["m_score"] = beneish_m_score(cur, prev)
                out["m_score_alert"] = out["m_score"] > BENEISH_THRESHOLD
                out["sloan_accruals"] = sloan_accruals(cur, prev)
                out["revenue_growth"] = cur["revenue"] / prev["revenue"] - 1
                out["receivables_growth"] = cur["receivables"] / prev["receivables"] - 1
                out["dso_change"] = out["dso"] - dso(prev)
            rows.append(out)
    return pd.DataFrame(rows)
