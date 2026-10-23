"""Offline test setup: Korean mode, sibling-module imports, a throwaway wiki dir."""

import os
import sys
from pathlib import Path

import pytest

os.environ["WIKI_LANG"] = "ko"
os.environ.setdefault("OPENAI_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "llm_wiki_bench"))


@pytest.fixture
def wiki(tmp_path, monkeypatch):
    """Point bench_config at an empty wiki under tmp_path."""
    import bench_config as config
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    monkeypatch.setattr(config, "WIKI_DIR", wiki_dir)
    monkeypatch.setattr(config, "WIKI_LOG", wiki_dir / "log.md")
    return wiki_dir


def write_page(wiki_dir: Path, rel: str, body: str, aliases: str = "", tags: str = "") -> Path:
    path = wiki_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    kind = rel.split("/")[0]
    path.write_text(f"---\ntype: {kind}\naliases: [{aliases}]\ntags: [{tags}]\n---\n{body}", encoding="utf-8")
    return path
