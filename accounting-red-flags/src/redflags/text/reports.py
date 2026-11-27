"""Rapports annuels : configuration (data/reports.csv), extraction mise en cache, analyse."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .extract import Page, extract_pages
from .lexicon import Lexicon

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "data" / "reports.csv"
REPORTS_DIR = ROOT / "data" / "reports"
CACHE_DIR = ROOT / "data" / "cache"


def load_config(path: Path = CONFIG) -> pd.DataFrame:
    return pd.read_csv(path)


def management_report(row, reports_dir: Path = REPORTS_DIR, cache_dir: Path = CACHE_DIR) -> list[Page]:
    """Pages du rapport de gestion, extraites une fois puis relues depuis le cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / f"{Path(row['file']).stem}_{row['mgmt_first_page']}_{row['mgmt_last_page']}.json"
    if cache.exists():
        return [Page(**p) for p in json.loads(cache.read_text())]
    pages = extract_pages(reports_dir / row["file"], int(row["mgmt_first_page"]), int(row["mgmt_last_page"]))
    cache.write_text(json.dumps([p.__dict__ for p in pages], ensure_ascii=False))
    return pages


def text_indicators(lexicon: Lexicon, config: pd.DataFrame | None = None, **kw) -> pd.DataFrame:
    config = load_config() if config is None else config
    rows = []
    for _, r in config.iterrows():
        pages = management_report(r, **kw)
        stats = lexicon.analyze("\n".join(p.text for p in pages))
        rows.append({"company": r["company"], "year": r["year"], "pages": len(pages), **stats})
    return pd.DataFrame(rows)
