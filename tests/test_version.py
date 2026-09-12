"""The release workflow bumps pyproject.toml and _version.py together; this
keeps the two from drifting apart in between."""
from __future__ import annotations

from importlib.metadata import version

import thalovant_languages


def test_the_package_version_matches_the_distribution():
    assert thalovant_languages.__version__ == version("thalovant-languages")
