"""``asks``: whether a sentence asks something, by the language's own words."""
from __future__ import annotations

import pytest

import thalovant_languages as languages


@pytest.fixture(autouse=True)
def _installed_data(monkeypatch):
    monkeypatch.delenv(languages.ENV_OVERRIDE, raising=False)
    languages.refresh()
    yield
    languages.refresh()


@pytest.mark.parametrize("text, lang", [
    ("what time is it", "en-US"), ("is it going to rain", "en"), ("do i need a jacket", "en-GB"),
    ("quelle heure est-il", "fr-FR"), ("il est quelle heure", "fr"), ("où est mon téléphone", "fr-CA"),
    ("on mange à quelle heure ce soir", "fr"),
    ("Tu as pensé à acheter du pain ?", "fr"), ("今日は雨？", "ja"), ("هل ستمطر غدا؟", "ar"),
])
def test_a_question_is_one(text, lang):
    assert languages.asks(text, lang)


@pytest.mark.parametrize("text, lang", [
    ("il fait beau aujourd'hui, on va se promener.", "fr"), ("c'est bruyant dehors avec les travaux", "fr"),
    ("je crois que le chat dort sur le canapé", "fr"), ("passe-moi le sel s'il te plaît", "fr"),
    ("turn off the lights", "en"), ("the dog needs a walk after dinner", "en-US"),
    ("my phone battery is almost dead", "en"), ("", "en"), ("   ", "fr"),
])
def test_a_statement_is_not(text, lang):
    assert not languages.asks(text, lang)


def test_a_language_nothing_describes_only_has_the_question_mark():
    assert not languages.asks("nuqDaq 'oH puchpa''e'", "tlh")
    assert languages.asks("nuqDaq 'oH puchpa''e'?", "tlh")


def test_with_no_language_every_described_language_is_tried():
    assert languages.asks("quelle heure est-il", None)
    assert languages.asks("what time is it", None)
    assert not languages.asks("turn off the lights", None)


def test_a_checkout_named_by_the_environment_decides(tmp_path, monkeypatch):
    tree = tmp_path / "languages"
    (tree / "xq").mkdir(parents=True)
    (tree / "xq" / "language.yaml").write_text(
        "question_openers: [zob]\nquestion_words_anywhere: [zib]\nquestion_patterns: ['\\bza [a-z]+ zu\\b']\n",
        encoding="utf-8")
    (tree / "scripts.yaml").write_text((languages.DATA_ROOT / "scripts.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv(languages.ENV_OVERRIDE, str(tree))
    languages.refresh()
    assert languages.asks("zob lumi", "xq") and languages.asks("lumi zib lumi", "xq") and languages.asks("za lumi zu", "xq")
    assert not languages.asks("lumi lumi", "xq")
    assert not languages.asks("what time is it", "en")
