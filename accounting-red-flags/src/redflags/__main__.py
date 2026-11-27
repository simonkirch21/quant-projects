"""Ligne de commande.

    python -m redflags analyze --financials data/financials.csv --reports data/reports/
    python -m redflags analyze ... --llm          (mode Claude, si ANTHROPIC_API_KEY est définie)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

from . import financials, indicators, report, score
from .text import llm as llm_mode
from .text.extract import sentences, words
from .text.lexicon import DEFAULT_PATH, Lexicon
from .text.reports import load_config, management_report, text_indicators


def _grams(s: str, n: int = 5) -> set:
    toks = re.sub(r"[^a-z]+", " ", s.lower()).split()
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def _quotes(lex, config, reports_dir, per_report=4):
    """Phrases NOUVELLES par rapport au rapport de l'année précédente : moins de 30 % de
    leurs suites de 5 mots y figuraient déjà (le texte repris chaque année n'apprend
    rien). Classées par nombre de mots juridiques ou incertains."""
    out = {}
    cats = ("Litigious", "Uncertainty")
    by_key = {(r["company"], r["year"]): r for _, r in config.iterrows()}
    for (company, year), r in by_key.items():
        prev = by_key.get((company, year - 1))
        if prev is None:
            continue
        old = set()
        for p in management_report(prev, reports_dir=reports_dir):
            old |= _grams(p.text.replace("\n", " "))
        scored = []
        for p in management_report(r, reports_dir=reports_dir):
            for s in sentences(p.text):
                g = _grams(s)
                if not g or len(s) > 400 or len(g & old) / len(g) > 0.3:
                    continue                    # phrase reprise (même reformulée) de l'année précédente
                hits = {w for w in words(s) if any(w.upper() in lex.sets[c] for c in cats)}
                if len(hits) >= 2:
                    scored.append((len(hits), p.number, s, hits))
        scored.sort(key=lambda x: -x[0])
        out[(company, year)] = [(pg, s, h) for _, pg, s, h in scored[:per_report]]
    return out


def analyze(args) -> int:
    fin = financials.load(args.financials)
    problems = financials.check(fin)
    if problems:
        print("Anomalies dans les données :\n- " + "\n- ".join(problems))
        return 1
    ind = indicators.compute(fin)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    text = quotes = llm_flags = None
    config = load_config(args.config)
    reports_dir = Path(args.reports)
    if Path(args.lexicon).exists() and reports_dir.exists():
        lex = Lexicon.load(args.lexicon)
        text = text_indicators(lex, config, reports_dir=reports_dir)
        quotes = {k: v for k, v in _quotes(lex, config, reports_dir).items() if k[0] == "Wirecard" or args.all_quotes}
        text.to_csv(out / "text_scores.csv", index=False)
    else:
        print("Dictionnaire ou rapports absents : volet texte ignoré (voir scripts/download_data.py).")

    if args.llm:
        if not llm_mode.available():
            print("--llm demandé mais ANTHROPIC_API_KEY n'est pas définie : mode Claude ignoré.")
        else:
            ex = llm_mode.RedFlagExtractor()
            rows, rejected = [], 0
            for _, r in config.iterrows():
                ok, bad = ex.extract(management_report(r, reports_dir=reports_dir))
                rows += [{"company": r["company"], "year": r["year"], **f} for f in ok]
                rejected += len(bad)
            llm_flags = pd.DataFrame(rows)
            llm_flags.attrs["analyzed"] = list(zip(config["company"], config["year"]))
            llm_flags.to_csv(out / "llm_red_flags.csv", index=False)
            print(f"Mode Claude : {len(rows)} signaux vérifiés, {rejected} citations introuvables rejetées.")

    sig = score.signal_table(ind, fin, text, llm_flags)
    ind.to_csv(out / "indicators.csv", index=False)
    sig.to_csv(out / "signals.csv", index=False)
    (out / "report.html").write_text(report.build(ind, sig, text, quotes, llm_flags), encoding="utf-8")
    print(sig[["company", "year", "signaux_allumes", "signaux_calculables", "score"]].to_string(index=False))
    print(f"\nRapport : {out / 'report.html'}")
    return 0


def main(argv=None) -> int:
    root = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(prog="redflags", description="Signaux d'alerte comptables")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="calculer les indicateurs et produire le rapport")
    a.add_argument("--financials", default=root / "data" / "financials.csv")
    a.add_argument("--reports", default=root / "data" / "reports")
    a.add_argument("--config", default=root / "data" / "reports.csv")
    a.add_argument("--lexicon", default=DEFAULT_PATH)
    a.add_argument("--out", default=root / "outputs")
    a.add_argument("--llm", action="store_true", help="activer le mode Claude (ANTHROPIC_API_KEY requise)")
    a.add_argument("--all-quotes", action="store_true", help="citations du mode dictionnaire pour toutes les sociétés")
    args = p.parse_args(argv)
    return analyze(args)


if __name__ == "__main__":
    sys.exit(main())
