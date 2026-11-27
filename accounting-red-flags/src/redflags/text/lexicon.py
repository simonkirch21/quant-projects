"""Analyse de texte par dictionnaire : Loughran et McDonald (2011).

Le dictionnaire de Loughran-McDonald classe les mots selon leur sens en
finance (« liability » ou « tax » n'y sont pas négatifs, contrairement aux
dictionnaires généralistes). Licence : usage de recherche non commercial ;
il n'est pas inclus dans le dépôt, voir scripts/download_data.py.

Indicateurs, pour 1 000 mots :
- négatif, positif, incertitude, litigieux, modal fort, modal faible ;
- ton net = (positif - négatif) / (positif + négatif) ;
- indice de Fog (Gunning) = 0,4 x (mots par phrase + 100 x part des mots de 3 syllabes ou plus).
  Plus il est élevé, plus le texte est difficile à lire ; Li (2008) associe un rapport
  difficile à lire à des résultats moins persistants (dissimulation possible).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .extract import sentences, to_prose, words

CATEGORIES = ["Negative", "Positive", "Uncertainty", "Litigious", "Strong_Modal", "Weak_Modal"]
DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "lexicon" / "Loughran-McDonald_MasterDictionary_1993-2025.csv"


class Lexicon:
    def __init__(self, word_sets: dict[str, set[str]], syllables: dict[str, int] | None = None):
        self.sets = {k: {w.upper() for w in v} for k, v in word_sets.items()}
        self.syllables = {k.upper(): v for k, v in (syllables or {}).items()}

    @classmethod
    def load(cls, path: str | Path = DEFAULT_PATH) -> "Lexicon":
        df = pd.read_csv(path, keep_default_na=False, usecols=["Word", "Syllables", *CATEGORIES])
        sets = {c: set(df.loc[df[c] != 0, "Word"]) for c in CATEGORIES}
        return cls(sets, dict(zip(df["Word"], df["Syllables"])))

    def count_syllables(self, word: str) -> int:
        w = word.upper()
        if w in self.syllables:
            return int(self.syllables[w])
        # Approximation : groupes de voyelles, « e » final muet
        groups = re.findall(r"[aeiouy]+", word.lower())
        n = len(groups) - (1 if word.lower().endswith("e") and len(groups) > 1 else 0)
        return max(n, 1)

    def analyze(self, text: str) -> dict:
        prose = to_prose(text)
        toks = [w.upper() for w in words(prose)]
        n = len(toks)
        if n == 0:
            return {"words": 0}
        out = {"words": n}
        for c in CATEGORIES:
            out[c.lower()] = 1000 * sum(t in self.sets[c] for t in toks) / n
        pos, neg = out["positive"], out["negative"]
        out["net_tone"] = (pos - neg) / (pos + neg) if pos + neg else 0.0
        sents = sentences(text)
        complex_share = sum(self.count_syllables(t) >= 3 for t in toks) / n
        words_per_sentence = n / max(len(sents), 1)
        out["fog"] = 0.4 * (words_per_sentence + 100 * complex_share)
        return out

    def flagged_sentences(self, text: str, category: str = "Uncertainty", top: int = 5) -> list[tuple[int, str]]:
        """Phrases contenant le plus de mots de la catégorie (pour illustrer le rapport)."""
        scored = []
        for s in sentences(text):
            k = sum(w.upper() in self.sets[category] for w in words(s))
            if k:
                scored.append((k, s))
        return sorted(scored, key=lambda x: -x[0])[:top]
