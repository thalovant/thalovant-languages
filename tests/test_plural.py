"""CLDR plural rules, read from the file as CLDR wrote them and evaluated here.

The evaluator is small on purpose, so it is checked two ways: against what
the rules say for the languages whose forms are well known, and -- when
Babel is installed, as the dev extra does -- against Babel's own reading of
CLDR for every language shipped, on a spread of counts.
"""
from __future__ import annotations

import pytest

import thalovant_languages as languages
from thalovant_languages import _plural


@pytest.fixture(autouse=True)
def _installed_data(monkeypatch):
    monkeypatch.delenv(languages.ENV_OVERRIDE, raising=False)
    languages.refresh()
    yield
    languages.refresh()


def test_the_well_known_forms():
    assert [languages.plural_category("en", n) for n in (0, 1, 2)] == ["other", "one", "other"]
    assert [languages.plural_category("fr", n) for n in (0, 1, 2)] == ["one", "one", "other"]
    assert [languages.plural_category("ru", n) for n in (1, 2, 5, 11, 21, 22, 25, 111)] == [
        "one", "few", "many", "many", "one", "few", "many", "many"]
    assert [languages.plural_category("ar", n) for n in (0, 1, 2, 3, 11, 100)] == [
        "zero", "one", "two", "few", "many", "other"]
    assert [languages.plural_category("pl", n) for n in (1, 2, 5, 22)] == ["one", "few", "many", "few"]
    assert [languages.plural_category("ja", n) for n in (1, 2)] == ["other", "other"]


def test_a_language_without_rules_keeps_one_and_other():
    assert languages.plural_category("tlh", 1) == "one"
    assert languages.plural_category("tlh", 2) == "other"
    assert languages.plural_category(None, 1) == "one"


def test_a_language_with_one_form_for_every_count_says_so():
    """CLDR describes Japanese with "other" alone; an empty table is that
    statement, and is not the guess an undescribed language gets."""
    assert languages.language("ja")["plural"] == {}
    assert [languages.plural_category("ja", n) for n in (0, 1, 2)] == ["other", "other", "other"]
    assert languages.plural_category("tlh", 1) == "one"


def test_every_rule_shipped_parses():
    for tag in languages.described():
        for category, rule in (languages.language(tag).get("plural") or {}).items():
            assert category in _plural.CATEGORIES, (tag, category)
            _plural.parse(rule)


@pytest.mark.parametrize("rule, n, expected", [
    ("n = 1", 1, True), ("n = 1", 2, False),
    ("i = 0..1", 0, True), ("i = 0..1", 2, False),
    ("n % 10 = 2..4 and n % 100 != 12..14", 22, True), ("n % 10 = 2..4 and n % 100 != 12..14", 12, False),
    ("n = 0 or n != 1 and n % 100 = 1..19", 19, True), ("n = 0 or n != 1 and n % 100 = 1..19", 20, False),
    ("v = 0 and i = 1", 1, True), ("v != 0", 1, False),
    ("n mod 10 is 1 and n mod 100 is not 11", 21, True), ("n in 2..4", 3, True), ("n not in 2..4", 3, False),
    ("n within 0..2", 2, True), ("", 7, True), ("@integer 1", 5, True),
])
def test_the_rule_syntax(rule, n, expected):
    assert _plural.parse(rule)(n) is expected


@pytest.mark.parametrize("rule", ["n = ", "x = 1", "n = 1 and", "n ~ 1", "n = 1..", "1 = n"])
def test_a_rule_this_module_cannot_read_says_so(rule):
    with pytest.raises(_plural.PluralRuleError):
        _plural.parse(rule)


def test_against_babel_on_babel_s_own_rule_text():
    """Babel re-serialises CLDR's rules in the legacy spelling ("v in 0 and
    i mod 10 in 2..4") and evaluates them with its own parser. Handing that
    text to this evaluator and comparing the answers, for every locale Babel
    knows and a spread of counts, checks the evaluator rather than the data,
    whichever CLDR release either side carries."""
    pytest.importorskip("babel")
    from babel.core import Locale
    from babel.localedata import locale_identifiers

    counts = list(range(0, 130)) + [199, 200, 201, 1000, 1001, 1000000, 1000001, 2000000]
    compared = 0
    for identifier in sorted(locale_identifiers()):
        if "_" in identifier:
            continue  # the language carries the rule; regions repeat it
        rules = dict(Locale.parse(identifier).plural_form.rules)
        for n in counts:
            assert _plural.category(rules, n) == Locale.parse(identifier).plural_form(n), (identifier, n)
        compared += 1
    assert compared > 100, f"only {compared} languages compared"
