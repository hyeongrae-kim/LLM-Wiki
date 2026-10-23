"""Checks on the committed example articles (converter output)."""

import json
import re
import unicodedata
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "assembly_spc"
pytestmark = pytest.mark.skipif(not EXAMPLES.exists(), reason="examples not generated")


def _articles():
    return sorted(EXAMPLES.glob("*/*.md"))


def test_titles_are_unique_and_documents_are_clean():
    titles = []
    for path in _articles():
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        assert not raw.startswith(b"\xef\xbb\xbf"), path
        assert unicodedata.is_normalized("NFC", text), path
        assert len(text) <= 6500, path
        titles.append(re.search(r'^title: "(.+)"$', text, re.MULTILINE).group(1)[:60])
    assert len(titles) == len(set(titles))


def test_manifest_matches_files():
    manifest = json.loads((EXAMPLES / "manifest.json").read_text(encoding="utf-8"))
    for name in manifest["full"] + manifest["small"]:
        assert (EXAMPLES / "articles" / name).exists(), name
    for name in manifest["add"]:
        assert (EXAMPLES / "add" / name).exists(), name
    assert set(manifest["small"]) <= set(manifest["full"])
