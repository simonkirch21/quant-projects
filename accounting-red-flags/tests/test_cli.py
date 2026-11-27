from redflags.__main__ import main


def test_cli_runs_without_reports_or_llm(tmp_path, capsys):
    """Sans PDF ni dictionnaire, la commande produit quand même les indicateurs et le rapport."""
    code = main(["analyze", "--reports", str(tmp_path / "absent"), "--lexicon", str(tmp_path / "absent.csv"),
                 "--out", str(tmp_path), "--llm"])
    assert code == 0
    assert (tmp_path / "report.html").exists() and (tmp_path / "signals.csv").exists()
    out = capsys.readouterr().out
    assert "volet texte ignoré" in out and "ANTHROPIC_API_KEY" in out
