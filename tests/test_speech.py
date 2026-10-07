"""The pronunciation repairs do what they say and nothing else.

Applied the way the satellite applies them: each rule of the language, in
order, case-insensitive, on the text before it reaches the synthesiser.
"""
from __future__ import annotations

import re

import pytest

import thalovant_languages as languages


@pytest.fixture(autouse=True)
def _installed_data(monkeypatch):
    monkeypatch.delenv(languages.ENV_OVERRIDE, raising=False)
    languages.refresh()
    yield
    languages.refresh()


def said(text: str, tag: str) -> str:
    for rule in languages.language(tag).get("speech_substitutions") or ():
        text = re.sub(rule["pattern"], rule["replace"], text, flags=re.IGNORECASE)
    return text


# The sign of a negative number -------------------------------------------------

# The word espeak-ng says for a plain "-3" in each language that has the rule.
MINUS = {
    "en": "minus", "fr": "moins", "es": "menos", "de": "minus", "it": "meno", "pt": "menos",
    "nl": "min", "ca": "menys", "eu": "minus", "da": "minus", "sv": "minus", "nb": "minus",
    "fi": "miinus", "pl": "minus", "cs": "mínus", "sk": "mínus", "sl": "minus", "ro": "minus",
    "ru": "минус", "uk": "мінус", "bg": "минус", "el": "μείον", "tr": "eksi", "hu": "mínusz",
    "is": "mínus", "lv": "mīnus", "et": "miinus", "lb": "minus", "cy": "minws", "sq": "minus",
    "sr": "минус", "id": "minus", "vi": "âm", "ka": "მინუს", "hy": "հանած", "fa": "منفی",
    "ar": "سالب", "he": "מינוס", "hi": "ऋण", "sw": "kasoro", "ko": "마이너스", "ne": "ऋणात्मक",
}

# A hyphen that is not a sign: after a letter, a digit or a unit.
NOT_A_SIGN = [
    "vingt-trois", "rendez-vous", "sub-23", "COVID-19", "UTC-5",
    "3-5", "de 3 - 5", "3°-5°", "10%-20%", "(3)-5",
    "2025-09-27", "27-09-2025", "06-12-34-56-78", "+33 6-12-34-56-78", "514-555-1234",
    "5−3",
]


@pytest.mark.parametrize("text,expected", [
    ("minimum -3 C", "minimum moins 3 C"),
    ("minimum -3°C", "minimum moins 3°C"),
    ("minimum −3 degrés", "minimum moins 3 degrés"),
    ("Il fera -3,5 degrés", "Il fera moins 3,5 degrés"),
    ("entre -12 et −5", "entre moins 12 et moins 5"),
    ("(-3)", "(moins 3)"),
    ("-3 ce matin", "moins 3 ce matin"),
])
def test_french_says_the_minus_of_a_negative_number(text, expected):
    assert said(text, "fr-FR") == expected
    assert said(text, "fr-CA") == expected


@pytest.mark.parametrize("tag", sorted(MINUS))
def test_every_language_with_the_rule_says_its_own_minus(tag):
    word = MINUS[tag]
    assert said("-3", tag) == f"{word} 3"
    assert said("−3", tag) == f"{word} 3", "the Unicode minus too"
    assert said("-3,5 °C", tag) == f"{word} 3,5 °C"
    assert said("-3.5", tag) == f"{word} 3.5"


@pytest.mark.parametrize("tag", sorted(MINUS))
def test_a_hyphen_that_is_not_a_sign_is_left_alone(tag):
    for text in NOT_A_SIGN:
        assert said(text, tag) == text, (tag, text)


def test_a_language_without_the_rule_is_untouched():
    assert said("-3", "ja") == "-3"
    assert said("-3", "tlh") == "-3"


# Devanagari: a word often ends in a vowel sign, a combining mark that \w does
# not match, so the hyphen after it has to be seen as following a letter.
DEVANAGARI_NOT_A_SIGN = ["कक्षा-3", "कक्षा−3", "पेज-2", "कि-3", "संख्या-१२", "धारा-370"]


@pytest.mark.parametrize("tag", ["hi", "ne"])
def test_a_hyphen_after_a_devanagari_vowel_sign_is_left_alone(tag):
    for text in DEVANAGARI_NOT_A_SIGN:
        assert said(text, tag) == text, (tag, text)


@pytest.mark.parametrize("tag", ["hi", "ne"])
def test_a_devanagari_sentence_still_says_its_minus(tag):
    word = MINUS[tag]
    assert said("तापमान -3°C", tag) == f"तापमान {word} 3°C"
    assert said("आज (−5) है", tag) == f"आज ({word} 5) है"


# The loanword "hub" --------------------------------------------------------------

# Lines the satellite says, in the words its translations use for the hub.
@pytest.mark.parametrize("tag,text,expected", [
    ("de", "Der Hub hat nicht rechtzeitig geantwortet.", "Der Habb hat nicht rechtzeitig geantwortet."),
    ("de", "Ich konnte den Hub nicht erreichen.", "Ich konnte den Habb nicht erreichen."),
    ("da", "Jeg kunne ikke få forbindelse til hubben.", "Jeg kunne ikke få forbindelse til habben."),
    ("es", "El hub no ha respondido a tiempo.", "El jab no ha respondido a tiempo."),
    ("it", "Non riesco a raggiungere l'hub.", "Non riesco a raggiungere l'ab."),
    ("pt", "O hub não respondeu a tempo.", "O rábi não respondeu a tempo."),
    ("pt-PT", "O hub não respondeu a tempo.", "O rábi não respondeu a tempo."),
    ("ro", "Nu am putut contacta hubul.", "Nu am putut contacta habul."),
    ("tr", "Hub'a ulaşamadım.", "hab'a ulaşamadım."),
    ("id", "Saya tidak bisa terhubung ke hub.", "Saya tidak bisa terhubung ke hab."),
    ("pl", "Nie ma połączenia z hubem.", "Nie ma połączenia z habem."),
])
def test_the_loanword_hub_is_said_the_way_people_say_it(tag, text, expected):
    assert said(text, tag) == expected


# The word itself and its endings only: Spanish "hubo" is "there was".
@pytest.mark.parametrize("tag,text", [
    ("de", "Der Hubschrauber landet gleich."),
    ("de", "Hubert ruft an."),
    ("es", "Hubo un problema."),
    ("es", "Si hubiera tiempo, iría."),
    ("pt", "Hubert chegou."),
    ("pl", "Hubert dzwonił."),
    ("id", "Saya tidak bisa terhubung."),
])
def test_a_word_that_only_starts_with_hub_is_left_alone(tag, text):
    assert said(text, tag) == text
