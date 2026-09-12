# thalovant-languages

Every word a Thalovant component's rule turns on, for every language the
fleet supports, in one place and out of every codebase.

A voice satellite waits on "turn off the" because "the" is a continuation
word. An intent listing closes "quelle heure est-il" with a question mark
because "quelle" opens a question, and reads "volume {level} percent" aloud
as "volume cinquante pour cent" in French. A French synthesiser is told to
say "onze minutes" where it would swallow a consonant. Each of those is a
fact about a language, not about the program that needs it, and each used
to be a constant in whichever program needed it first. Here they are data:
one directory per language, read by the SDK and by the satellite, and a new
language is a directory in this repository rather than an edit to a program.

## Layout

```
src/thalovant_languages/languages/
  scripts.yaml            what a writing system does that no word list can
  en-US/language.yaml     English
  fr-FR/language.yaml     French
  es/language.yaml        Spanish, every region (bare tag)
  de/ it/ pt/ nl/         German, Italian, Portuguese, Dutch
  tr/ az/                 Turkish, Azerbaijani (the dotless i)
```

A directory is named by a BCP-47 tag: bare (`es`) when what it says holds
for every region, regional (`en-US`) when it does not. Every key in a
language file is optional. A language that states none of them gets no
rule at all, never another language's: a wrong question mark reads as a
defect, a bare line does not.

| Key | What a component does with it |
|---|---|
| `continuation_words` | a partial transcript ending here is mid-thought; the endpoint waits |
| `trailing_words` | a registered phrase ending here is a prefix waiting for an entity, not a sentence |
| `question_openers` | a phrase opening here is a question |
| `question_words_anywhere` | a phrase holding one of these anywhere is a question |
| `question_patterns` | regular expressions (case-insensitive) that make a phrase a question |
| `written_forms` | words spelled their own way once a phrase is set as a sentence (`i: I`) |
| `plural` | which counts take which form of a counted string; a count listed nowhere is `other` |
| `slot_examples` | what a slot becomes when a pattern is read aloud |
| `lowercase_map` | applied to an all-capitals transcript, in order, before `lower()` |
| `speech_substitutions` | rewrites for what a synthesiser is known to mispronounce (`pattern`, `replace`, `why`) |

`scripts.yaml` lists the scripts written without spaces (a partial
transcript in one is a single "word", so characters are counted), the
scripts where one character is a syllable (how a synthesiser weighs a
sentence), and the marks that close a sentence or break a clause, spaced
and unspaced.

## Use

```python
import thalovant_languages as languages

languages.language("fr-CA")["continuation_words"]   # the French file
languages.words("en", "trailing_words")             # lower-cased, as a set
languages.language("zh")                            # {} -- nothing describes it
languages.script_pattern("unspaced").search("今天") # a character of an unspaced script
languages.marks("sentence_ends", "spaced")          # ".!?…;"
```

A language is found by the matcher the rest of OVOS uses
(`ovos_spec_tools.language`): `fr-CA` reads `fr-FR`, `pt-BR` reads `pt`,
and a language nothing describes gets an empty mapping.

`THALOVANT_LANGUAGES_DIR=/path/to/checkout/src/thalovant_languages/languages`
reads a checkout instead of the installed data, for trying a language before
it is released; `languages.refresh()` forgets what was read after changing it.

## Adding a language

1. Add `src/thalovant_languages/languages/<tag>/language.yaml` with the keys
   the language needs, each with a comment saying why the words are there.
   Quote a word YAML would read as something else (`"on"`, `"no"`).
2. Run `thalovant-languages check` (or `pytest`). It refuses a key no
   component reads, a pattern that does not compile, a plural category that
   is not one, and a list holding a boolean.
3. Open a pull request. Merging to `main` releases the package; the SDK and
   the satellite pick the language up when they move their pin.

## Who reads it

- `thalovant` (the Python SDK): `thalovant.listing` sets a registered pattern
  the way a person reads it, ranks phrases, and reads slots aloud.
- `thalovant-voice` (the satellite): the semantic endpoint's continuation
  words, the lower-casing of an all-capitals transcript, the plural forms of
  its own counted text, and the synthesiser's pronunciation repairs.

Nothing here parses dates, numbers or colours; the OVOS parsers do that for
skills on the hub. Contractions come from `ovos-utterance-normalizer`, which
already carries them.
