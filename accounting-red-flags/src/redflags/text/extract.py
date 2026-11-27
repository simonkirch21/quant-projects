"""Extraction du texte des rapports annuels PDF (pdfplumber).

Mises en page à colonnes (doubles pages d'Adyen 2018, deux colonnes de
Wirecard 2018) : quand une gouttière verticale sépare le texte, la zone est
coupée en deux et lue colonne par colonne, jusqu'à deux niveaux. Sinon, les
lignes des deux colonnes s'entremêleraient et fausseraient les phrases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pdfplumber


@dataclass
class Page:
    number: int        # numéro de page dans le fichier PDF (1 = première)
    text: str


def _clean(text: str) -> str:
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)        # mots coupés en fin de ligne
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    return text.strip()


def _gutter(region) -> float | None:
    """Abscisse de la gouttière entre deux colonnes, ou None.

    On ignore les en-têtes et pieds de page (10 % du haut et du bas), puis on cherche,
    entre 20 % et 80 % de la largeur et avec au moins 15 % des mots de chaque côté,
    la position traversée par le moins de mots. Il y a deux colonnes si au plus 3 %
    des mots la traversent."""
    x0, top, x1, bottom = region.bbox
    h = bottom - top
    words = [w for w in region.extract_words() if top + 0.10 * h < w["top"] < bottom - 0.10 * h]
    if len(words) < 40:
        return None
    best, best_n = None, None
    width = x1 - x0
    for i in range(61):
        x = x0 + width * (0.20 + 0.60 * i / 60)
        left = sum(1 for w in words if w["x1"] <= x)
        right = sum(1 for w in words if w["x0"] >= x)
        if min(left, right) < 0.15 * len(words):
            continue                      # il faut du texte des deux côtés
        n = sum(1 for w in words if w["x0"] < x < w["x1"])
        if best_n is None or n < best_n:
            best, best_n = x, n
    if best is not None and best_n <= 0.03 * len(words):
        return best
    return None


def _region_text(region, depth: int = 0) -> str:
    x = _gutter(region) if depth < 2 else None
    if x is not None:
        x0, top, x1, bottom = region.bbox
        return (_region_text(region.crop((x0, top, x, bottom)), depth + 1) + "\n"
                + _region_text(region.crop((x, top, x1, bottom)), depth + 1))
    return region.extract_text() or ""


def _page_text(page) -> str:
    """Texte d'une page, colonne par colonne (doubles pages et pages à deux colonnes)."""
    return _region_text(page)


def extract_pages(path, first: int = 1, last: int | None = None) -> list[Page]:
    with pdfplumber.open(path) as pdf:
        last = last or len(pdf.pages)
        return [Page(i, _clean(_page_text(pdf.pages[i - 1]))) for i in range(first, last + 1)]


def to_prose(text: str) -> str:
    """Recolle les lignes en paragraphes et retire les lignes de chiffres (tableaux)."""
    lines = [ln for ln in text.split("\n") if len(re.findall(r"[A-Za-z]{2,}", ln)) >= 3]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"“(])", to_prose(text))
    return [s for s in parts if len(re.findall(r"[A-Za-z]+", s)) >= 4]


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*[A-Za-z]|[A-Za-z]", text)
