"""Télécharge les rapports annuels (data/reports.csv) et le dictionnaire Loughran-McDonald.

Ces fichiers ne sont pas dans le dépôt : droits d'auteur des rapports, et licence
du dictionnaire réservée à un usage de recherche non commercial.
Lancement depuis le dossier accounting-red-flags :  python scripts/download_data.py
"""

from pathlib import Path
import re
import sys

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
LM_URL = "https://drive.usercontent.google.com/download?id=1iq2RUf8qGFEAk1g8wQntP3habOnR3fXF&export=download&confirm=t"
LM_FILE = ROOT / "data" / "lexicon" / "Loughran-McDonald_MasterDictionary_1993-2025.csv"


def fetch(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"déjà présent : {dest.name}")
        return
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    if dest.suffix == ".pdf" and not r.content.startswith(b"%PDF"):
        # Pages Adyen : le lien mène à une page qui contient le lien du PDF (brand.adyen.com)
        for link in sorted(set(re.findall(r"https://brand\.adyen\.com/api/asset/[^\"' ]+/download", r.text))):
            pdf = requests.get(link, timeout=120)
            if pdf.content.startswith(b"%PDF") and len(pdf.content) > 1_000_000:
                r = pdf
                break
        else:
            raise RuntimeError(f"PDF introuvable pour {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    print(f"téléchargé : {dest.name} ({len(r.content) / 1e6:.1f} Mo)")


def main() -> int:
    for _, row in pd.read_csv(ROOT / "data" / "reports.csv").iterrows():
        fetch(row["url"], ROOT / "data" / "reports" / row["file"])
    fetch(LM_URL, LM_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
