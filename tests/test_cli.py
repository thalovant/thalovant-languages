"""`thalovant-languages check` is the gate a checkout runs before a release."""
from __future__ import annotations

import pytest

import thalovant_languages as languages
from thalovant_languages.__main__ import main


@pytest.fixture(autouse=True)
def _installed_data(monkeypatch):
    monkeypatch.delenv(languages.ENV_OVERRIDE, raising=False)
    languages.refresh()
    yield
    languages.refresh()


def test_check_passes_on_the_shipped_tree(capsys):
    assert main(["check"]) == 0
    assert "sound" in capsys.readouterr().out


def test_check_fails_on_a_broken_tree(tmp_path, capsys):
    (tmp_path / "xx").mkdir()
    (tmp_path / "xx" / "language.yaml").write_text("nonsense: [1]\n", encoding="utf-8")
    assert main(["check", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "not a key" in captured.err and "scripts.yaml: missing" in captured.err
    assert "problem(s)" in captured.out


def test_list_and_show(capsys):
    assert main(["list"]) == 0
    listed = capsys.readouterr().out.split()
    assert "en-US" in listed and "fr-FR" in listed
    assert main(["show", "fr-CA"]) == 0
    shown = capsys.readouterr().out
    assert "continuation_words:" in shown and "speech_substitutions: 1" in shown
    assert main(["show", "zh"]) == 1
