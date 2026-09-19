"""Regional matching against the real shipped data, including Chinese scripts."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import thalovant_languages as languages

REGIONS = {
    "en": "US CA GB AU NZ", "fr": "FR CA BE CH", "es": "ES MX AR CO US",
    "de": "DE AT CH", "pt": "PT BR AO MZ", "nl": "NL BE", "sv": "SE FI",
    "zh": "CN TW SG HK MO",
}


@pytest.fixture(autouse=True)
def shipped_data(monkeypatch):
    monkeypatch.delenv(languages.ENV_OVERRIDE, raising=False)
    languages.refresh()
    yield
    languages.refresh()


@pytest.mark.parametrize("tag", [f"{base}-{region}" for base, regions in REGIONS.items()
                                 for region in regions.split()])
def test_common_regions_resolve_and_accept_tag_spelling_variants(tag):
    data = languages.language(tag)
    assert data and data.get("continuation_words"), tag
    assert languages.language(tag.lower().replace("-", "_")) == data
    if not tag.startswith("zh-"):
        assert data["continuation_words"] == languages.language(tag.split("-")[0])["continuation_words"]


@pytest.mark.parametrize("tag", ["zh-TW", "zh-HK", "zh-MO", "zh-Hant", "zh-Hant-TW"])
def test_traditional_chinese_has_usable_words_and_inherits_plural_rules(tag):
    assert languages.asks("什麼時候出發", tag)
    assert "這" in languages.words(tag, "continuation_words")
    assert "这" not in languages.words(tag, "continuation_words")
    assert languages.language(tag)["plural"] == languages.language("zh")["plural"]
    assert languages.plural_category(tag, 1) == "other"


@pytest.mark.parametrize("tag", ["zh-CN", "zh-SG", "zh-Hans", "zh-Hans-CN"])
def test_simplified_chinese_remains_usable(tag):
    assert languages.asks("什么时候出发", tag)
    assert "这" in languages.words(tag, "continuation_words")


def test_chinese_script_overlays_are_reproducible():
    script = Path(__file__).resolve().parents[1] / "scripts/derive_chinese.py"
    subprocess.run([sys.executable, str(script), "--check"], check=True)
