#!/usr/bin/env python3
"""Derive every language file from the sources that already know the answer.

Nothing in `languages/` is written by hand any more. This script reads:

  Universal Dependencies treebanks   which words a language's sentences end
                                      on and which they never do; which words
                                      open a question; which are written
                                      capitalised
  CLDR plurals.json                   the plural rules of every locale
  Unicode PropList, Scripts,          which marks close a sentence or break a
    SpecialCasing                     clause, which scripts have no spaces,
                                      which languages lower-case their own way
  overrides/<tag>.yaml                what only a person knows: how a slot is
                                      read aloud, what a voice mispronounces

and writes `src/thalovant_languages/languages/<tag>/language.yaml` and
`scripts.yaml`, each with a header naming the sources and their versions.
Run it, review the diff, commit.

    python scripts/derive.py --ud /path/to/ud-treebanks-v2.18 \\
        --cldr plurals.json --unicode /path/with/PropList.txt

Every threshold below is a number a reader can argue with, and is written
into the header so the argument has its facts.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import unicodedata

import langcodes
import yaml
from ovos_spec_tools.language import standardize_lang

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "thalovant_languages" / "languages"
OVERRIDES = ROOT / "overrides"

# -- what a treebank says ---------------------------------------------------------

# The closed classes a sentence does not end on: a determiner, a preposition,
# a conjunction, an auxiliary, a possessive. Universal Dependencies tags them
# the same way in every language.
CONTINUATION_UPOS = {"DET", "ADP", "CCONJ", "SCONJ", "AUX"}
# Universal features carry "possessive" and "interrogative".
POSSESSIVE = "Poss=Yes"
# Punctuation that closes a question, by script. Greek closes one with a
# semicolon, and only Greek does.
QUESTION_MARKS = {"?", "？", "؟", "՞", "¿", "‽", "⁇", "⁈", "⁉"}
GREEK_QUESTION_MARKS = {";", ";"}

# Thresholds. A form is a continuation word when it is closed-class nearly
# every time it appears and almost never the last word of a sentence; it
# opens a question when a sentence starting with it usually is one; it asks
# from anywhere when a sentence holding it almost always is one.
MIN_COUNT = 20
CLOSED_CLASS_PURITY = 0.8
# English "is" ends 3% of its sentences ("here it is") and "on" 6% ("turn it
# on"): the first is worth waiting on, the second is not. A false hold costs
# one silence window; a false fire costs the whole interaction.
MAX_FINAL_RATIO = 0.04
MAX_WORDS = 80
# An interrogative word (PronType=Int) opens a question by definition. Any
# other word does when a sentence starting with it usually is one -- and an
# auxiliary sooner, because "do", "have" and "could" open a question far more
# often in a request to a machine than in the prose the treebanks hold.
OPENER_MIN = 50
OPENER_PRECISION = 0.6
AUXILIARY_OPENER_PRECISION = 0.4
INTERROGATIVE_MIN = 20
ANYWHERE_MIN = 10
ANYWHERE_PRECISION = 0.85
CAPITAL_MIN = 20
# "I" is lower case in the treebanks of learners and children; nine in ten is
# the written form.
CAPITAL_RATIO = 0.9


class Tally:
    def __init__(self) -> None:
        self.treebanks: set[str] = set()
        self.sentences = 0
        self.questions = 0
        self.total: collections.Counter[str] = collections.Counter()
        self.closed: collections.Counter[str] = collections.Counter()
        self.final: collections.Counter[str] = collections.Counter()
        self.first: collections.Counter[str] = collections.Counter()
        self.first_q: collections.Counter[str] = collections.Counter()
        self.anywhere: collections.Counter[str] = collections.Counter()
        self.anywhere_q: collections.Counter[str] = collections.Counter()
        self.mid_total: collections.Counter[str] = collections.Counter()
        self.mid_capital: collections.Counter[str] = collections.Counter()
        self.mid_form: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        self.upos: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
        self.interrogative: collections.Counter[str] = collections.Counter()
        self.pron: collections.Counter[str] = collections.Counter()
        self.pron_poss: collections.Counter[str] = collections.Counter()
        self.possessive: collections.Counter[str] = collections.Counter()
        self.form_treebanks: dict[str, set[str]] = collections.defaultdict(set)


def _is_word(form: str) -> bool:
    core = form.replace("'", "").replace("’", "").replace("-", "")
    return bool(core) and core.isalpha()


def _read_sentences(path: pathlib.Path):
    """Tokens per sentence, as (form, upos, feats, misc)."""
    tokens: list[tuple[str, str, str, str]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            if not line.strip():
                if tokens:
                    yield tokens
                tokens = []
                continue
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 10 or "-" in cols[0] or "." in cols[0]:
                continue  # a multiword range or an empty node
            tokens.append((cols[1], cols[3], cols[5], cols[9]))
    if tokens:
        yield tokens


def tally_treebanks(ud_root: pathlib.Path) -> dict[str, Tally]:
    tallies: dict[str, Tally] = collections.defaultdict(Tally)
    for path in sorted(ud_root.rglob("*.conllu")):
        code = path.name.split("_", 1)[0]
        if not langcodes.tag_is_valid(code):
            continue
        tag = standardize_lang(code)
        tally = tallies[tag]
        treebank = path.name.split("-ud-")[0]
        tally.treebanks.add(treebank)
        greek = tag == "el"
        for tokens in _read_sentences(path):
            # A treebank splits "can't" into "ca" and "n't", "we're" into "we"
            # and "'re": neither half is a word anybody says on its own.
            clitic = set()
            for index, (form, _, _, misc) in enumerate(tokens):
                if form[:1] in "'’" or form.lower() in ("n't", "n’t"):
                    clitic.add(index)
                    if index:
                        clitic.add(index - 1)
            words = [(f, u, x) for i, (f, u, x, _) in enumerate(tokens) if u != "PUNCT" and i not in clitic]
            if not words:
                continue
            marks = {f for f, u, _, _ in tokens if u == "PUNCT"}
            last_punct = next((f for f, u, _, _ in reversed(tokens) if u == "PUNCT"), "")
            is_question = last_punct in QUESTION_MARKS or (greek and last_punct in GREEK_QUESTION_MARKS) \
                or bool(marks & {"¿"})
            tally.sentences += 1
            tally.questions += is_question
            seen: set[str] = set()
            for index, (form, upos, feats) in enumerate(words):
                low = form.lower()
                if not _is_word(low):
                    continue
                tally.total[low] += 1
                tally.form_treebanks[low].add(treebank)
                tally.upos[low][upos] += 1
                if "PronType=Int" in feats:
                    tally.interrogative[low] += 1
                if upos == "PRON":
                    tally.pron[low] += 1
                    tally.pron_poss[low] += POSSESSIVE in feats
                tally.possessive[low] += POSSESSIVE in feats
                if upos in CONTINUATION_UPOS or (upos == "PRON" and POSSESSIVE in feats) \
                        or (upos == "PART" and "PronType=Int" not in feats and low in ("to",)):
                    tally.closed[low] += 1
                if index == len(words) - 1:
                    tally.final[low] += 1
                if index == 0:
                    tally.first[low] += 1
                    tally.first_q[low] += is_question
                else:
                    if upos in CONTINUATION_UPOS | {"PRON"}:
                        tally.mid_total[low] += 1
                        if form[:1].isupper():
                            tally.mid_capital[low] += 1
                            tally.mid_form[low][form] += 1
                if low not in seen:
                    seen.add(low)
                    tally.anywhere[low] += 1
                    tally.anywhere_q[low] += is_question
    return dict(tallies)


OPENER_UPOS = {"PRON", "DET", "ADV", "AUX", "SCONJ", "PART"}


def _dominant(tally: Tally, form: str) -> str:
    return tally.upos[form].most_common(1)[0][0] if tally.upos[form] else ""


def _widespread(tally: Tally, form: str) -> bool:
    """Seen in more than one treebank, when the language has several: a
    word one corpus alone uses is that corpus's spelling, period or typo."""
    return len(tally.treebanks) < 3 or len(tally.form_treebanks[form]) >= 2


def derive_words(tally: Tally) -> dict:
    out: dict = {}
    continuation = []
    for form, count in tally.total.most_common():
        if count < MIN_COUNT:
            break
        if not _widespread(tally, form):
            continue
        closed = tally.closed[form]
        # A possessive pronoun in a treebank that writes no features is
        # still the same word: once half its pronoun uses are marked
        # possessive, all of them count.
        if tally.pron[form] and tally.pron_poss[form] / tally.pron[form] >= 0.5:
            closed += tally.pron[form] - tally.pron_poss[form]
        purity = closed / count
        final = tally.final[form] / count
        if purity >= CLOSED_CLASS_PURITY and final <= MAX_FINAL_RATIO:
            continuation.append(form)
        if len(continuation) >= MAX_WORDS:
            break
    if continuation:
        out["continuation_words"] = continuation
        # A registered phrase that ends on a possessive ("coupe le son") or
        # an auxiliary ("qué hora es") is a whole sentence more often than a
        # prefix waiting for an entity; a listing leaves those out.
        trailing = [
            form for form in continuation
            if tally.possessive[form] / tally.total[form] < 0.5
            and tally.upos[form]["AUX"] / tally.total[form] < 0.5]
        if trailing:
            out["trailing_words"] = trailing
    openers = []
    for form, count in tally.first.most_common():
        if count < OPENER_MIN and tally.interrogative[form] < INTERROGATIVE_MIN:
            continue
        if not _widespread(tally, form):
            continue
        precision = tally.first_q[form] / max(1, count)
        interrogative = (tally.interrogative[form] >= INTERROGATIVE_MIN
                         and tally.interrogative[form] / tally.total[form] >= 0.2)
        auxiliary = tally.upos[form]["AUX"] / max(1, tally.total[form]) >= 0.3
        if _dominant(tally, form) not in OPENER_UPOS and not interrogative and not auxiliary:
            continue
        if interrogative or precision >= OPENER_PRECISION or (auxiliary and precision >= AUXILIARY_OPENER_PRECISION):
            openers.append(form)
    if openers:
        out["question_openers"] = openers
    anywhere = []
    if tally.questions:
        for form, count in tally.anywhere.most_common():
            if count < ANYWHERE_MIN:
                break
            if not _widespread(tally, form):
                continue
            if tally.interrogative[form] >= INTERROGATIVE_MIN and tally.anywhere_q[form] / count >= ANYWHERE_PRECISION:
                anywhere.append(form)
    if anywhere:
        out["question_words_anywhere"] = anywhere
    written = {}
    for form, count in tally.mid_total.most_common():
        if count < CAPITAL_MIN:
            break
        if not _widespread(tally, form):
            continue
        if tally.mid_capital[form] / count >= CAPITAL_RATIO:
            written[form] = tally.mid_form[form].most_common(1)[0][0]
    if written:
        out["written_forms"] = written
    return out


# -- what CLDR says -----------------------------------------------------------------

def cldr_plurals(path: pathlib.Path) -> tuple[dict[str, dict[str, str]], str]:
    data = json.loads(path.read_text(encoding="utf-8"))["supplemental"]
    version = str(data["version"]["_cldrVersion"])
    out: dict[str, dict[str, str]] = {}
    for locale, rules in data["plurals-type-cardinal"].items():
        if locale == "root":
            continue
        try:
            tag = standardize_lang(locale)
        except Exception:
            continue
        # A locale CLDR describes with "other" alone (Japanese, Chinese...)
        # has one form for every count: an empty table says so, where a
        # missing one would mean nothing is known.
        table = {}
        for key, rule in rules.items():
            name = key.replace("pluralRule-count-", "")
            if name == "other":
                continue
            table[name] = rule.split("@", 1)[0].strip()
        out[tag] = table
    return out, version


# -- what Unicode says --------------------------------------------------------------

UNSPACED_SCRIPTS = ("Han", "Hiragana", "Katakana", "Thai", "Lao", "Khmer", "Myanmar", "Tibetan")
SYLLABIC_SCRIPTS = ("Han", "Hiragana", "Katakana", "Hangul")
# Common-script punctuation that lives in CJK text, where nothing follows a mark.
UNSPACED_PUNCTUATION_BLOCKS = ((0x3000, 0x303F), (0xFF00, 0xFFEF))


def _unicode_version(path: pathlib.Path) -> str:
    head = path.read_text(encoding="utf-8").splitlines()[0]
    m = re.search(r"-(\d+\.\d+\.\d+)\.txt", head)
    return m.group(1) if m else "unknown"


def _property_ranges(path: pathlib.Path, wanted: str) -> list[tuple[int, int]]:
    ranges = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        span, prop = [part.strip() for part in line.split(";")[:2]]
        if prop != wanted:
            continue
        first, _, last = span.partition("..")
        ranges.append((int(first, 16), int(last or first, 16)))
    return sorted(ranges)


def _script_of(ranges_by_script: dict[str, list[tuple[int, int]]], cp: int) -> str:
    for script, ranges in ranges_by_script.items():
        if any(low <= cp <= high for low, high in ranges):
            return script
    return "Common"


def _merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for low, high in sorted(ranges):
        if out and low <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], high))
        else:
            out.append((low, high))
    return out


def derive_scripts(unicode_dir: pathlib.Path, override: dict) -> tuple[dict, str]:
    proplist = unicode_dir / "PropList.txt"
    scripts_file = unicode_dir / "Scripts.txt"
    version = _unicode_version(proplist)
    by_script: dict[str, list[tuple[int, int]]] = {}
    for name in set(UNSPACED_SCRIPTS) | set(SYLLABIC_SCRIPTS):
        by_script[name] = _merge(_property_ranges(scripts_file, name))
    terminal = [cp for low, high in _property_ranges(proplist, "Sentence_Terminal") for cp in range(low, high + 1)]
    punctuation = [cp for low, high in _property_ranges(proplist, "Terminal_Punctuation") for cp in range(low, high + 1)]

    def unspaced(cp: int) -> bool:
        return _script_of(by_script, cp) in UNSPACED_SCRIPTS or any(
            low <= cp <= high for low, high in UNSPACED_PUNCTUATION_BLOCKS)

    also_spaced = str(override.get("sentence_ends_also_spaced") or "")
    sentence_spaced = "".join(chr(cp) for cp in terminal if not unspaced(cp))
    sentence_unspaced = "".join(chr(cp) for cp in terminal if unspaced(cp))
    clause_cps = [cp for cp in punctuation if cp not in set(terminal) and chr(cp) not in also_spaced]
    clause_spaced = "".join(chr(cp) for cp in clause_cps if not unspaced(cp))
    clause_unspaced = "".join(chr(cp) for cp in clause_cps if unspaced(cp))

    def blocks(names: tuple[str, ...]) -> list[dict]:
        out = []
        for name in names:
            for low, high in by_script[name]:
                out.append({"name": name, "first": f"U+{low:04X}", "last": f"U+{high:04X}"})
        return out

    data = {
        "unspaced": {"ranges": blocks(UNSPACED_SCRIPTS),
                     "characters_per_word": int(override.get("characters_per_word", 2))},
        "syllabic": {"ranges": blocks(SYLLABIC_SCRIPTS),
                     "letters_per_character": int(override.get("letters_per_character", 5))},
        "sentence_ends": {"spaced": sentence_spaced + "".join(c for c in also_spaced if c not in sentence_spaced),
                          "unspaced": sentence_unspaced},
        "clause_breaks": {"spaced": clause_spaced, "unspaced": clause_unspaced},
    }
    return data, version


def special_casing(path: pathlib.Path) -> dict[str, dict[str, str]]:
    """Per language, the lower-case mappings that differ from the default and
    hold unconditionally: Turkish and Azeri's dotted and dotless i."""
    out: dict[str, dict[str, str]] = collections.defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(";")]
        if len(parts) < 5 or not parts[4]:
            continue  # unconditional entries are the default algorithm's
        conditions = parts[4].split()
        languages = [c for c in conditions if langcodes.tag_is_valid(c) and c.islower()]
        # Turkish "I" lower-cases to dotless "ı" unless a combining dot above
        # follows it (Not_Before_Dot), which a transcript never carries; any
        # other context (After_I, More_Above...) is not a plain map.
        if not languages or set(conditions) - set(languages) - {"Not_Before_Dot"}:
            continue
        upper = "".join(chr(int(cp, 16)) for cp in parts[0].split())
        lower = "".join(chr(int(cp, 16)) for cp in parts[1].split())
        if lower and lower != upper.lower():
            out[standardize_lang(languages[0])][upper] = lower
    return dict(out)


# -- putting a file together ---------------------------------------------------------

def load_override(tag: str) -> dict:
    path = OVERRIDES / f"{tag}.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _dump(path: pathlib.Path, header: list[str], data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100)
    path.write_text("".join(f"# {line}\n" if line else "#\n" for line in header) + body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ud", type=pathlib.Path, required=True, help="an unpacked ud-treebanks-vX.Y directory")
    parser.add_argument("--cldr", type=pathlib.Path, required=True, help="CLDR's supplemental/plurals.json")
    parser.add_argument("--unicode", type=pathlib.Path, required=True,
                        help="a directory with PropList.txt, Scripts.txt and SpecialCasing.txt")
    parser.add_argument("--out", type=pathlib.Path, default=OUT)
    args = parser.parse_args()

    ud_version = re.search(r"v(\d+\.\d+)", args.ud.name)
    ud_version = ud_version.group(1) if ud_version else "unknown"
    print("reading treebanks...", file=sys.stderr)
    tallies = tally_treebanks(args.ud)
    plurals, cldr_version = cldr_plurals(args.cldr)
    casing = special_casing(args.unicode / "SpecialCasing.txt")
    unicode_version = _unicode_version(args.unicode / "PropList.txt")

    scripts_override = load_override("scripts")
    scripts, _ = derive_scripts(args.unicode, scripts_override)
    _dump(args.out / "scripts.yaml", [
        "Generated by scripts/derive.py -- do not edit; edit overrides/scripts.yaml and rerun.",
        f"Sources: Unicode {unicode_version} (PropList.txt Sentence_Terminal and Terminal_Punctuation,",
        "Scripts.txt). Scripts written without spaces between words, scripts where one",
        "character is a syllable, the marks that close a sentence and the marks that break",
        "a clause, spaced (whitespace follows) or unspaced (nothing follows).",
        f"Overrides: {', '.join(f'{k}={v!r}' for k, v in scripts_override.items()) or 'none'}.",
    ], scripts)

    tags = sorted(set(tallies) | set(plurals) | set(casing)
                  | {p.stem for p in OVERRIDES.glob("*.yaml") if p.stem != "scripts"})
    # A fresh tree: what is not derived any more is not kept.
    if args.out.is_dir():
        for old in args.out.iterdir():
            if old.is_dir() and old.name not in tags:
                for f in old.iterdir():
                    f.unlink()
                old.rmdir()
    written = 0
    for tag in tags:
        data: dict = {}
        sources = []
        tally = tallies.get(tag)
        if tally is not None:
            data.update(derive_words(tally))
            sources.append(f"Universal Dependencies {ud_version} ({', '.join(sorted(tally.treebanks))}; "
                           f"{tally.sentences} sentences, {tally.questions} questions)")
        if tag in plurals:
            data["plural"] = plurals[tag]
            sources.append(f"CLDR {cldr_version} plural rules")
        if tag in casing:
            data["lowercase_map"] = casing[tag]
            sources.append(f"Unicode {unicode_version} SpecialCasing")
        override = load_override(tag)
        if override:
            # A key replaces what was derived; a key spelled "+key" adds to it,
            # for the one word a source could not know belongs in a list.
            for key, value in override.items():
                if key.startswith("+") and isinstance(value, list):
                    merged = list(data.get(key[1:]) or [])
                    data[key[1:]] = merged + [v for v in value if v not in merged]
                else:
                    data[key] = value
            sources.append(f"overrides/{tag}.yaml ({', '.join(override)})")
        if not data:
            continue
        try:
            name = langcodes.Language.get(tag).display_name()
        except Exception:  # the names package is optional; the tag is enough
            name = tag
        header = [
            f"{name} ({tag}). Generated by scripts/derive.py -- do not edit; edit overrides/{tag}.yaml and rerun.",
            "Sources: " + "; ".join(sources) + ".",
            "Thresholds: a word counts once it appears in two treebanks (when the language has three);",
            f"a continuation word is closed-class {CLOSED_CLASS_PURITY:.0%} of the time and",
            f"the last word of a sentence at most {MAX_FINAL_RATIO:.0%} of the time, seen {MIN_COUNT}+ times;",
            "a trailing word is a continuation word that is neither a possessive nor an auxiliary;",
            f"a question opener is interrogative (PronType=Int, {INTERROGATIVE_MIN}+ times) or starts a",
            f"question {OPENER_PRECISION:.0%} of the time it starts a sentence ({AUXILIARY_OPENER_PRECISION:.0%} for an auxiliary);",
            f"a question word anywhere is interrogative and sits in a question {ANYWHERE_PRECISION:.0%} of the time;",
            f"a written form is capitalised mid-sentence {CAPITAL_RATIO:.0%} of the time.",
        ]
        _dump(args.out / tag / "language.yaml", header, data)
        written += 1
    print(f"wrote {written} languages under {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
