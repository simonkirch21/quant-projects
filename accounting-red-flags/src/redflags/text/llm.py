"""Mode Claude (facultatif) : détection de signaux d'alerte dans le texte, avec
citations exactes vérifiées par code.

Actif seulement si la variable d'environnement ANTHROPIC_API_KEY existe. Les
pages sont envoyées par paquets ; Claude renvoie un JSON contraint par un
schéma (structured outputs). Chaque citation est ensuite recherchée dans le
texte source : une citation introuvable est rejetée (anti-hallucination), une
citation trouvée sur une autre page que celle annoncée est corrigée.
Les réponses sont mises en cache sur disque : relancer l'analyse ne repaie pas
les mêmes appels.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path

from .extract import Page

MODEL = "claude-opus-5-5"
PROMPT_VERSION = "v1"
CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "llm_cache"

FLAG_TYPES = [
    "changement_methode_comptable", "partenaires_tiers_opaques", "langage_vague_tresorerie",
    "parties_liees", "changement_auditeur", "reserves_audit_ou_enquete", "croissance_par_acquisitions",
    "indicateurs_non_ifrs", "autre",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "red_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": FLAG_TYPES},
                    "citation_exacte": {"type": "string"},
                    "page": {"type": "integer"},
                    "gravite": {"type": "integer"},
                    "explication": {"type": "string"},
                },
                "required": ["type", "citation_exacte", "page", "gravite", "explication"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["red_flags"],
    "additionalProperties": False,
}

SYSTEM = """You are a forensic accounting analyst reviewing the management report of an annual report, the way a short seller or a credit analyst would.

Report only genuine warning signs supported by the text: changes in accounting methods or estimates, reliance on opaque third parties or partners, vague or evasive language about cash and its location, related-party transactions, auditor changes or qualifications, regulatory or special investigations, growth that depends on acquisitions, heavy use of non-IFRS "adjusted" metrics. Ordinary business risks that every company discloses are not warning signs.

For each warning sign:
- citation_exacte: copy one sentence or clause from the text VERBATIM, character for character, in the original language. Never paraphrase, translate, shorten with ellipses or merge two passages. Each page starts with a [page N] marker; quote text from a single page.
- page: the N of the [page N] marker where the quote appears.
- gravite: 1 (minor) to 5 (severe).
- explication: one or two sentences in French explaining why it is a warning sign.

If there is no genuine warning sign, return an empty list."""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def locate_quote(quote: str, pages: list[Page]) -> int | None:
    """Numéro de la page qui contient la citation (à la casse, aux espaces et aux
    guillemets près), ou None si elle n'existe nulle part."""
    q = _norm(quote)
    if len(q) < 15:
        return None
    for p in pages:
        if q in _norm(p.text):
            return p.number
    return None


def verify(flags: list[dict], pages: list[Page]) -> tuple[list[dict], list[dict]]:
    """Sépare les signaux vérifiés des citations introuvables (hallucinations)."""
    ok, rejected = [], []
    for f in flags:
        found = locate_quote(f["citation_exacte"], pages)
        if found is None:
            rejected.append(f)
            continue
        ok.append({**f, "page_annoncee": f["page"], "page": found,
                   "gravite": min(max(int(f["gravite"]), 1), 5)})
    return ok, rejected


def chunks(pages: list[Page], size: int = 8) -> list[list[Page]]:
    return [pages[i:i + size] for i in range(0, len(pages), size)]


def _render(chunk: list[Page]) -> str:
    return "\n\n".join(f"[page {p.number}]\n{p.text}" for p in chunk)


def available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


class RedFlagExtractor:
    def __init__(self, client=None, cache_dir: Path = CACHE_DIR, model: str = MODEL):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client, self.cache_dir, self.model = client, Path(cache_dir), model
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, text: str) -> Path:
        key = hashlib.sha256(f"{self.model}|{PROMPT_VERSION}|{SYSTEM}|{text}".encode()).hexdigest()
        return self.cache_dir / f"{key}.json"

    def _call(self, text: str) -> list[dict]:
        path = self._cache_path(text)
        if path.exists():
            return json.loads(path.read_text())
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                       # repli sur un autre modèle en cas de refus
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM,
            messages=[{"role": "user", "content": text}],
        )
        if response.stop_reason == "refusal":
            flags = []
        elif response.stop_reason == "max_tokens":
            raise RuntimeError("réponse tronquée (max_tokens) : réduire la taille des paquets de pages")
        else:
            raw = next(b.text for b in response.content if b.type == "text")
            flags = json.loads(raw)["red_flags"]
        path.write_text(json.dumps(flags, ensure_ascii=False))
        return flags

    def extract(self, pages: list[Page], chunk_size: int = 8) -> tuple[list[dict], list[dict]]:
        """Signaux vérifiés et citations rejetées, pour tout un rapport."""
        verified, rejected = [], []
        for chunk in chunks(pages, chunk_size):
            ok, bad = verify(self._call(_render(chunk)), chunk)
            verified += ok
            rejected += bad
        return verified, rejected
