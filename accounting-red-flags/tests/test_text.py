import json
from types import SimpleNamespace

import pytest

from redflags.text.extract import Page, sentences, to_prose, words
from redflags.text.lexicon import Lexicon
from redflags.text.llm import RedFlagExtractor, locate_quote, verify

LEX = Lexicon({
    "Negative": {"LOSS", "DECLINE"}, "Positive": {"STRONG", "GROWTH"},
    "Uncertainty": {"MAY", "APPROXIMATELY"}, "Litigious": {"LITIGATION"},
    "Strong_Modal": {"WILL"}, "Weak_Modal": {"MIGHT"},
}, syllables={"APPROXIMATELY": 6, "LITIGATION": 4})


# --- Extraction et lexique -------------------------------------------------------

def test_prose_drops_number_rows_and_joins_lines():
    text = "Revenue grew strongly in the\nyear under review.\n1,234 5,678 9,012\nEBITDA 410.3 560.5"
    assert to_prose(text) == "Revenue grew strongly in the year under review."


def test_sentences_and_words():
    s = sentences("The company may grow. Revenue rose by ten percent in Europe. Ok.")
    assert s == ["The company may grow.", "Revenue rose by ten percent in Europe."]
    assert words("Wirecard's cash-flow rose") == ["Wirecard's", "cash-flow", "rose"]


def test_lexicon_counts_per_thousand_words():
    text = "Strong growth will continue but litigation may cause a loss in the coming year now."
    r = LEX.analyze(text)
    assert r["words"] == 15
    assert r["positive"] == pytest.approx(2 / 15 * 1000)
    assert r["negative"] == pytest.approx(1 / 15 * 1000)
    assert r["uncertainty"] == pytest.approx(1 / 15 * 1000)
    assert r["net_tone"] == pytest.approx((2 - 1) / (2 + 1))


def test_fog_index_by_hand():
    # 1 phrase de 10 mots, dont 2 de 3 syllabes ou plus (approximately, litigation)
    text = "Approximately all litigation was settled by the team this year."
    r = LEX.analyze(text)
    assert r["fog"] == pytest.approx(0.4 * (10 / 1 + 100 * 2 / 10))


def test_syllable_fallback_for_unknown_words():
    assert LEX.count_syllables("payment") == 2
    assert LEX.count_syllables("cake") == 1


# --- Mode Claude : vérification des citations ---------------------------------------

PAGES = [
    Page(10, "Our acquiring business in Asia relies on third-party\npartners for processing."),
    Page(11, "Cash is held in escrow accounts with a trustee bank."),
]


def test_locate_quote_tolerates_line_breaks_quotes_and_case():
    assert locate_quote("relies on third-party partners for processing", PAGES) == 10
    assert locate_quote("CASH IS HELD IN ESCROW ACCOUNTS", PAGES) == 11


def test_hallucinated_quote_is_rejected_and_wrong_page_is_corrected():
    flags = [
        {"type": "partenaires_tiers_opaques", "citation_exacte": "relies on third-party partners",
         "page": 11, "gravite": 7, "explication": "..."},
        {"type": "langage_vague_tresorerie", "citation_exacte": "cash was moved to undisclosed accounts",
         "page": 11, "gravite": 5, "explication": "..."},
    ]
    ok, rejected = verify(flags, PAGES)
    assert len(ok) == 1 and len(rejected) == 1
    assert ok[0]["page"] == 10 and ok[0]["page_annoncee"] == 11
    assert ok[0]["gravite"] == 5                       # ramenée dans l'intervalle 1-5
    assert rejected[0]["citation_exacte"].startswith("cash was moved")


class FakeClient:
    """Imite client.beta.messages.create sans appel réseau, et compte les appels."""

    def __init__(self, payload):
        self.calls = 0
        self.payload = payload
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls += 1
        assert kwargs["output_config"]["format"]["type"] == "json_schema"
        return SimpleNamespace(stop_reason="end_turn",
                               content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


def test_extractor_verifies_quotes_and_caches_calls(tmp_path):
    payload = {"red_flags": [
        {"type": "langage_vague_tresorerie", "citation_exacte": "Cash is held in escrow accounts",
         "page": 11, "gravite": 4, "explication": "Trésorerie hors du bilan direct."},
        {"type": "autre", "citation_exacte": "This sentence does not exist anywhere",
         "page": 10, "gravite": 2, "explication": "Inventée."},
    ]}
    client = FakeClient(payload)
    ex = RedFlagExtractor(client=client, cache_dir=tmp_path)
    ok, rejected = ex.extract(PAGES, chunk_size=8)
    assert [f["page"] for f in ok] == [11] and len(rejected) == 1
    ex.extract(PAGES, chunk_size=8)                  # même texte : lu dans le cache
    assert client.calls == 1


def test_refusal_returns_no_flags(tmp_path):
    client = FakeClient({"red_flags": []})
    client.beta.messages.create = lambda **kw: SimpleNamespace(stop_reason="refusal", content=[])
    assert RedFlagExtractor(client=client, cache_dir=tmp_path).extract(PAGES) == ([], [])
