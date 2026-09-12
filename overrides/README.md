# overrides/

What only a person knows about a language, kept apart from what the sources
say. `scripts/derive.py` writes every `languages/<tag>/language.yaml` from
Universal Dependencies, CLDR and Unicode, then lays the file here of the
same name on top, key by key, and names it in the generated header.

Put here: how a slot is read aloud in the language, what a synthesiser
voice is known to mispronounce, a question pattern the treebanks cannot
express, a measured exception to a Unicode property. Do not put here a word
list you could derive: change the generator, or its thresholds, instead.

A key replaces what was derived. A key spelled `+key` (a list) adds to it
instead, for the one word a source could not know belongs in a list: the
French weather skill writes "à" as "a", so `+trailing_words: [a]`.
