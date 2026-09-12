"""The data tree is sound, and a language is found the way the rest of OVOS
finds one.

The first gate runs the same check a checkout runs before a release, on the
shipped tree: a misspelt key, a pattern that does not compile, a bare `on`
that YAML read as a boolean, fails here rather than on the first utterance
in that language. The rest pins what a consumer may rely on: regions read
their language's file, an undescribed language gets nothing, and a tree
named by the environment is read instead of the installed one.
"""
from __future__ import annotations

import pathlib

import pytest

import thalovant_languages as languages

FULL = {"continuation_words", "trailing_words", "question_openers", "plural", "slot_examples"}


@pytest.fixture(autouse=True)
def _installed_data(monkeypatch):
    monkeypatch.delenv(languages.ENV_OVERRIDE, raising=False)
    languages.refresh()
    yield
    languages.refresh()


def test_the_shipped_tree_passes_the_check():
    assert languages.check() == []


def test_the_check_names_what_is_wrong(tmp_path):
    bad = tmp_path / "xx"
    bad.mkdir()
    (bad / "language.yaml").write_text(
        "continuation_words: [the, on]\n"
        "question_patterns: ['(']\n"
        "plural: {some: [1]}\n"
        "colour_words: [red]\n"
        "lowercase_map: {a: A}\n",
        encoding="utf-8",
    )
    problems = languages.check(tmp_path)
    text = "\n".join(problems)
    assert "colour_words" in text and "not a key" in text
    assert "quote a word" in text, problems
    assert "does not compile" in text
    assert "'some' is not a category" in text
    assert "not upper to lower" in text
    assert "scripts.yaml: missing" in text


def test_the_languages_the_fleet_speaks_are_fully_described():
    for tag in ("en-US", "fr-FR"):
        missing = sorted(FULL - set(languages.language(tag)))
        assert not missing, (tag, missing)
    assert {"az", "de", "es", "it", "nl", "pt", "tr"} <= set(languages.described())


def test_a_region_reads_its_language_file():
    french = languages.language("fr-FR")
    assert french["continuation_words"]
    assert languages.language("fr-CA") == french
    assert languages.language("fr") == french
    assert languages.language("pt-BR") == languages.language("pt")
    assert languages.language("en-GB") == languages.language("en-US")
    assert languages.language("es-MX")["continuation_words"]


def test_a_language_nothing_describes_gets_no_rule_rather_than_another_language_s():
    assert languages.language("zh-CN") == {}
    assert languages.language("xx") == {}
    assert languages.language(None) == {}
    assert languages.language("") == {}


def test_word_lists_are_lower_cased_and_unite_when_no_language_is_named():
    assert "the" in languages.words("en", "trailing_words")
    assert "la" in languages.words("fr-CA", "trailing_words")
    everything = languages.words(None, "trailing_words")
    assert {"the", "la"} <= everything
    assert languages.words("zh", "trailing_words") == frozenset()


def test_the_turkic_lower_casing_map_is_ordered_upper_to_lower():
    for tag in ("tr", "az"):
        table = languages.language(tag)["lowercase_map"]
        assert list(table.items()) == [("İ", "i"), ("I", "ı")]


def test_script_classes_match_their_own_characters_and_nothing_else():
    unspaced = languages.script_pattern("unspaced")
    assert unspaced.search("今天") and unspaced.search("สวัสดี")
    assert not unspaced.search("hello") and not unspaced.search("안녕")
    syllabic = languages.script_pattern("syllabic")
    assert syllabic.search("안녕") and syllabic.search("今天")
    assert not syllabic.search("สวัสดี") and not syllabic.search("bonjour")
    assert not languages.script_pattern("no-such-kind").search("anything at all")
    assert int(languages.scripts()["unspaced"]["characters_per_word"]) >= 1


def test_the_marks_that_close_a_sentence_cover_every_script():
    assert "?" in languages.marks("sentence_ends", "spaced")
    assert "。" in languages.marks("sentence_ends", "unspaced")
    assert "," in languages.marks("clause_breaks", "spaced")
    assert languages.marks("no-such-kind", "spaced") == ""


def test_a_checkout_named_by_the_environment_is_read_instead(tmp_path, monkeypatch):
    """Trying a language before it is released: a directory, no code."""
    tree = tmp_path / "languages"
    (tree / "xq").mkdir(parents=True)
    (tree / "xq" / "language.yaml").write_text("continuation_words: [zu]\nplural: {one: [1]}\n",
                                               encoding="utf-8")
    (tree / "scripts.yaml").write_text(
        (languages.DATA_ROOT / "scripts.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv(languages.ENV_OVERRIDE, str(tree))
    languages.refresh()
    assert languages.root() == tree
    assert languages.described() == ("xq",)
    assert languages.language("xq-ZZ") == {"continuation_words": ["zu"], "plural": {"one": [1]}}
    assert languages.language("en") == {}
    assert languages.check() == []


def test_the_installed_tree_is_where_the_package_is():
    assert languages.DATA_ROOT == pathlib.Path(languages.__file__).resolve().parent / "languages"
    assert (languages.DATA_ROOT / "scripts.yaml").is_file()
