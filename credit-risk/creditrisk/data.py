"""Données : 30 000 titulaires de cartes de crédit à Taïwan (avril-septembre 2005).

Source : UCI Machine Learning Repository, « Default of Credit Card Clients »
(Yeh et Lien, 2009). Cible : défaut de paiement le mois suivant.

Choix éthiques et réglementaires : le sexe, la situation familiale et l'âge
ne sont PAS utilisés. Ce sont des critères de discrimination interdits ou
sensibles pour l'octroi de crédit (en France, article 225-1 du Code pénal ;
en Europe, directive 2004/113/CE et RGPD).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "credit_card_default.csv"
TARGET = "defaut"
EXCLUDED = ["SEX", "MARRIAGE", "AGE"]
PAY = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]   # retard de paiement, du plus récent au plus ancien
BILL = [f"BILL_AMT{i}" for i in range(1, 7)]                     # solde du relevé
PAYAMT = [f"PAY_AMT{i}" for i in range(1, 7)]                    # montant remboursé


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    return df.rename(columns={"default payment next month": TARGET})


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Variables explicatives construites à partir de l'historique de 6 mois.

    PAY_x : -2 = aucune utilisation, -1 = payé intégralement, 0 = crédit
    renouvelable utilisé normalement, 1 à 8 = mois de retard.
    """
    limit = df["LIMIT_BAL"]
    bill1 = df["BILL_AMT1"].clip(lower=0)
    delays = df[PAY].clip(lower=0)
    util = df[BILL].clip(lower=0).div(limit, axis=0)
    paid = df[PAYAMT].sum(axis=1)
    billed = df[BILL[1:]].clip(lower=0).sum(axis=1)      # factures remboursables par PAY_AMT1..5

    out = pd.DataFrame(index=df.index)
    out["retard_dernier_mois"] = df["PAY_0"]
    out["retard_max_6m"] = delays.max(axis=1)
    out["nb_mois_en_retard"] = (delays > 0).sum(axis=1)
    out["plafond"] = limit
    out["utilisation"] = (bill1 / limit).clip(upper=1.5)
    out["utilisation_moyenne_6m"] = util.mean(axis=1).clip(upper=1.5)
    out["hausse_utilisation"] = (util["BILL_AMT1"] - util["BILL_AMT6"]).clip(-1.5, 1.5)
    out["taux_remboursement_6m"] = np.where(billed > 0, paid / billed.where(billed > 0, 1), 1.0).clip(0, 2)
    out["dernier_remboursement"] = df["PAY_AMT1"]
    edu = df["EDUCATION"].where(df["EDUCATION"].isin([1, 2, 3]), 4)  # 4 = autre ou inconnu
    out["education"] = edu
    return out


def exposure_at_default(df: pd.DataFrame, ccf: float = 0.75) -> pd.Series:
    """EAD = montant utilisé + CCF x montant non utilisé (le client peut tirer
    sur sa ligne avant de faire défaut)."""
    drawn = df["BILL_AMT1"].clip(lower=0)
    undrawn = (df["LIMIT_BAL"] - drawn).clip(lower=0)
    return drawn + ccf * undrawn
