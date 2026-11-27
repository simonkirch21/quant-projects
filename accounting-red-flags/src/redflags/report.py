"""Rapport HTML autonome (un seul fichier, graphiques Plotly)."""

from __future__ import annotations

import html
import re

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .ratios import BENEISH_THRESHOLD
from .score import SIGNALS

COLORS = {"Wirecard": "#c0392b", "Adyen": "#2471a3"}
CSS = """body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:1100px;margin:30px auto;
color:#1f2328;line-height:1.5;padding:0 16px}h1{margin-bottom:0}.sub{color:#59636e;margin-top:4px}
table{border-collapse:collapse;margin:12px 0;font-size:14px}td,th{border:1px solid #d0d7de;padding:5px 9px;text-align:right}
th{background:#f6f8fa}td:first-child,th:first-child{text-align:left}.on{background:#f8d7da}.off{background:#d1e7dd}
.na{color:#999}mark{background:#ffe08a;padding:0 2px}blockquote{border-left:4px solid #d0d7de;margin:8px 0;
padding:4px 12px;color:#333;font-size:14px}.note{background:#fff8e1;border:1px solid #f0d58c;padding:10px 14px;border-radius:6px}"""


def _line(ind, col, title, ytitle, threshold=None, fmt=None):
    fig = go.Figure()
    for c, g in ind.groupby("company"):
        g = g.dropna(subset=[col])
        fig.add_trace(go.Scatter(x=g["year"], y=g[col], name=c, mode="lines+markers",
                                 line=dict(color=COLORS.get(c), width=3)))
    if threshold is not None:
        fig.add_hline(y=threshold[0], line_dash="dash", line_color="black", annotation_text=threshold[1])
    fig.update_layout(title=title, yaxis_title=ytitle, height=360, margin=dict(t=50, b=40),
                      xaxis=dict(dtick=1), legend=dict(orientation="h", y=-0.2))
    if fmt:
        fig.update_yaxes(tickformat=fmt)
    return fig


def _heatmap(sig):
    cols = [c for c in SIGNALS if c in sig]
    labels = [f"{r.company} {r.year}" for r in sig.itertuples()]
    z = sig[cols].to_numpy(dtype=float)
    fig = go.Figure(go.Heatmap(z=z, x=[SIGNALS[c][0] for c in cols], y=labels, zmin=0, zmax=1,
                               colorscale=[[0, "#d1e7dd"], [1, "#e35d6a"]], showscale=False, xgap=2, ygap=2,
                               hovertemplate="%{y}<br>%{x}<extra></extra>"))
    fig.update_layout(title="Signaux allumés (rouge) par société et par année (gris : non calculable)",
                      height=120 + 34 * len(labels), margin=dict(l=120, t=50, b=200), plot_bgcolor="#e5e5e5")
    fig.update_xaxes(tickangle=35)
    return fig


def _highlight(sentence: str, words: set[str]) -> str:
    out = html.escape(sentence)
    for w in sorted(words, key=len, reverse=True):
        out = re.sub(rf"\b({re.escape(w)})\b", r"<mark>\1</mark>", out, flags=re.I)
    return out


def _table(df: pd.DataFrame, formats: dict) -> str:
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = ""
    for _, r in df.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            cells.append(f"<td>{formats[c](v) if c in formats and pd.notna(v) else ('–' if pd.isna(v) else html.escape(str(v)))}</td>")
        body += "<tr>" + "".join(cells) + "</tr>"
    return f"<table><tr>{head}</tr>{body}</table>"


def build(ind, sig, text=None, quotes=None, llm=None, title="Signaux d'alerte comptables : Wirecard et Adyen") -> str:
    figs = [
        _line(ind, "m_score", "M-Score de Beneish", "M-Score", (BENEISH_THRESHOLD, "seuil -1,78")),
        _line(ind, "dso", "Délai d'encaissement des créances (DSO)", "jours", (120, "120 jours")),
        _line(ind, "debt_to_cash", "Dettes financières / trésorerie", "", (0.30, "30 %"), ".0%"),
        _line(ind, "z_double_prime", "Z'' d'Altman (sociétés non industrielles)", "Z''", (2.60, "zone saine > 2,60")),
    ]
    if text is not None:
        figs.append(_line(text, "net_tone", "Ton net du rapport de gestion (Loughran-McDonald)", "(pos - nég) / (pos + nég)"))
        figs.append(_line(text, "litigious", "Vocabulaire juridique (mots pour 1 000)", "pour 1 000 mots"))
        figs.append(_line(text, "fog", "Indice de lisibilité de Fog (plus haut = plus difficile)", "Fog"))
    figs.append(_heatmap(sig))

    parts = [f"<h1>{html.escape(title)}</h1>",
             "<p class='sub'>Rapport généré par <code>python -m redflags analyze</code>. Montants en millions d'euros, "
             "tirés des rapports annuels publiés (voir data/financials.csv pour la page de chaque chiffre).</p>",
             "<div class='note'><b>Lecture.</b> Un signal allumé n'est pas une preuve de fraude : c'est une question "
             "à poser. Les seuils non issus de la littérature ont été fixés en connaissant l'issue de Wirecard "
             "(biais rétrospectif).</div>",
             "<h2>Score composite</h2>",
             _table(sig[["company", "year", "signaux_allumes", "signaux_calculables", "score"]].rename(columns={
                 "company": "Société", "year": "Année", "signaux_allumes": "Signaux allumés",
                 "signaux_calculables": "Signaux calculables", "score": "Score"}),
                 {"Score": lambda v: f"{v:.0%}", "Signaux allumés": lambda v: f"{v:.0f}"})]
    for i, f in enumerate(figs):
        parts.append(f.to_html(full_html=False, include_plotlyjs=(i == 0)))
    show = ind[["company", "year", "m_score", "dso", "cash_conversion", "sloan_accruals", "debt_to_cash", "z_double_prime"]]
    parts += ["<h2>Indicateurs</h2>", _table(show.rename(columns={
        "company": "Société", "year": "Année", "m_score": "M-Score", "dso": "DSO (jours)",
        "cash_conversion": "CFO / résultat", "sloan_accruals": "Accruals", "debt_to_cash": "Dette / trésorerie",
        "z_double_prime": "Z''"}), {"M-Score": "{:.2f}".format, "DSO (jours)": "{:.0f}".format,
        "CFO / résultat": "{:.2f}".format, "Accruals": "{:.1%}".format, "Dette / trésorerie": "{:.0%}".format,
        "Z''": "{:.2f}".format})]
    if llm is not None and len(llm):
        parts.append("<h2>Signaux textuels vérifiés (mode Claude)</h2><p>Chaque citation a été retrouvée mot pour mot "
                     "dans le rapport ; les citations introuvables ont été rejetées.</p>")
        for r in llm.sort_values(["company", "year", "gravite"], ascending=[True, True, False]).itertuples():
            parts.append(f"<blockquote><b>{r.company} {r.year}, page {r.page}, gravité {r.gravite}/5 "
                         f"({html.escape(r.type)})</b><br>« {html.escape(r.citation_exacte)} »<br>"
                         f"<i>{html.escape(r.explication)}</i></blockquote>")
    if quotes:
        parts.append("<h2>Phrases nouvelles par rapport à l'année précédente, les plus chargées en vocabulaire juridique ou incertain (mode dictionnaire)</h2>")
        for (company, year), items in quotes.items():
            parts.append(f"<h3>{company} {year}</h3>")
            for page, sentence, words in items:
                parts.append(f"<blockquote><b>page {page}</b> : {_highlight(sentence, words)}</blockquote>")
    return f"<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'><title>{html.escape(title)}</title>" \
           f"<style>{CSS}</style></head><body>{''.join(parts)}</body></html>"
