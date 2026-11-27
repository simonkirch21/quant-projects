"""Indicateurs quantitatifs de manipulation comptable et de détresse financière.

Toutes les fonctions prennent un dictionnaire (ou une ligne de DataFrame) de
postes comptables, en millions, avec les noms du modèle data/template.csv.

Références :
- Beneish, M. (1999). The Detection of Earnings Manipulation. Financial Analysts Journal.
- Altman, E. (1968). Financial Ratios, Discriminant Analysis and the Prediction of
  Corporate Bankruptcy. Journal of Finance. Version Z'' (sociétés non industrielles) :
  Altman (1995, 2000).
- Sloan, R. (1996). Do Stock Prices Fully Reflect Information in Accruals and Cash
  Flows about Future Earnings? The Accounting Review.
"""

from __future__ import annotations

BENEISH_COEF = {
    "const": -4.84, "DSRI": 0.920, "GMI": 0.528, "AQI": 0.404, "SGI": 0.892,
    "DEPI": 0.115, "SGAI": -0.172, "TATA": 4.679, "LVGI": -0.327,
}
BENEISH_THRESHOLD = -1.78   # au-dessus : profil de manipulateur (modèle à 8 variables)


def _gross_margin(d) -> float:
    return (d["revenue"] - d["cost_of_sales"]) / d["revenue"]


def _soft_assets_share(d) -> float:
    """Part des actifs « mous » : ni courants, ni immobilisations corporelles, ni titres."""
    return 1 - (d["current_assets"] + d["ppe"] + d.get("securities", 0.0)) / d["total_assets"]


def _dep_rate(d) -> float:
    return d["depreciation"] / (d["depreciation"] + d["ppe"])


def beneish_components(cur, prev) -> dict:
    """Les 8 variables du M-Score pour l'année `cur`, comparée à `prev`."""
    return {
        # Créances / CA : un bond signale du chiffre d'affaires gonflé ou non encaissé
        "DSRI": (cur["receivables"] / cur["revenue"]) / (prev["receivables"] / prev["revenue"]),
        # Dégradation de la marge brute (> 1 : la marge baisse)
        "GMI": _gross_margin(prev) / _gross_margin(cur),
        # Hausse des actifs « mous » (coûts capitalisés, écarts d'acquisition…)
        "AQI": _soft_assets_share(cur) / _soft_assets_share(prev),
        # Croissance du chiffre d'affaires (la croissance crée une pression)
        "SGI": cur["revenue"] / prev["revenue"],
        # Ralentissement de l'amortissement (> 1 : on amortit moins vite)
        "DEPI": _dep_rate(prev) / _dep_rate(cur),
        # Frais commerciaux et administratifs rapportés au CA
        "SGAI": (cur["sga"] / cur["revenue"]) / (prev["sga"] / prev["revenue"]),
        # Hausse de l'endettement
        "LVGI": ((cur["current_liabilities"] + cur["long_term_debt"]) / cur["total_assets"])
                / ((prev["current_liabilities"] + prev["long_term_debt"]) / prev["total_assets"]),
        # Accruals totaux : bénéfice non converti en trésorerie
        "TATA": (cur["net_income"] - cur["cfo"]) / cur["total_assets"],
    }


def beneish_m_score(cur, prev) -> float:
    c = beneish_components(cur, prev)
    return BENEISH_COEF["const"] + sum(BENEISH_COEF[k] * v for k, v in c.items())


def altman_z(d) -> float:
    """Z-Score d'origine (1968), conçu pour les entreprises industrielles cotées.
    Zones : < 1,81 détresse ; 1,81 - 2,99 zone grise ; > 2,99 saine."""
    ta = d["total_assets"]
    return (1.2 * (d["current_assets"] - d["current_liabilities"]) / ta
            + 1.4 * d["retained_earnings"] / ta
            + 3.3 * d["ebit"] / ta
            + 0.6 * d["market_cap"] / d["total_liabilities"]
            + 1.0 * d["revenue"] / ta)


def altman_z_double_prime(d) -> float:
    """Z'' (1995) pour les sociétés non industrielles et de services : sans le ratio
    CA / actif (qui dépend trop du secteur) et avec les capitaux propres comptables.
    Zones : < 1,10 détresse ; 1,10 - 2,60 zone grise ; > 2,60 saine."""
    ta = d["total_assets"]
    return (6.56 * (d["current_assets"] - d["current_liabilities"]) / ta
            + 3.26 * d["retained_earnings"] / ta
            + 6.72 * d["ebit"] / ta
            + 1.05 * d["equity"] / d["total_liabilities"])


def z_zone(z: float, double_prime: bool = False) -> str:
    low, high = (1.10, 2.60) if double_prime else (1.81, 2.99)
    return "détresse" if z < low else "grise" if z <= high else "saine"


def sloan_accruals(cur, prev) -> float:
    """Accruals (méthode des flux) rapportés à l'actif moyen : (résultat net - CFO) / actif moyen.
    Sloan (1996) : les entreprises au plus fort taux d'accruals voient ensuite leurs
    bénéfices et leur cours décevoir."""
    return (cur["net_income"] - cur["cfo"]) / ((cur["total_assets"] + prev["total_assets"]) / 2)


def cash_conversion(d) -> float:
    """Flux de trésorerie d'exploitation / résultat net : < 1 durablement = bénéfice peu encaissé."""
    return d["cfo"] / d["net_income"]


def dso(d) -> float:
    """Délai moyen d'encaissement des créances clients, en jours."""
    return d["receivables"] / d["revenue"] * 365


def debt_to_cash(d) -> float:
    """Dettes financières / trésorerie. Emprunter (et payer des intérêts) tout en déclarant
    une trésorerie abondante est un signal classique des vendeurs à découvert : si l'argent
    existait vraiment, pourquoi s'endetter ?"""
    return d["interest_bearing_debt"] / d["cash"]
