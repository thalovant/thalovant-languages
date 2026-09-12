"""The release workflow bumps pyproject.toml and _version.py together; this
keeps the two from drifting apart in between."""
from __future__ import annotations

import pathlib
import tomllib

import thalovant_languages


def test_the_package_version_matches_the_project():
    pyproject = pathlib.Path(thalovant_languages.__file__).resolve().parents[2] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert thalovant_languages.__version__ == declared
