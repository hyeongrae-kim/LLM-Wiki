import argparse

import bench_config as config
import cli


def test_restore_brings_back_wiki_articles_cache_and_purpose(tmp_path, monkeypatch):
    # set_dataset rebinds these globals; let monkeypatch put them back afterwards.
    for name in ["_current_dataset", "WIKI_DIR", "RAW_DIR", "CACHE_FILE",
                 "WIKI_INDEX", "WIKI_OVERVIEW", "WIKI_LOG", "INGEST_LOG_DIR"]:
        monkeypatch.setattr(config, name, getattr(config, name))
    monkeypatch.setattr(config, "BASE_DIR", tmp_path)
    monkeypatch.setattr(cli, "REPO", tmp_path)
    args = argparse.Namespace(corpus="demo", name="built", lang=None, log_llm=False)

    config.set_dataset("demo")
    (config.WIKI_DIR / "index.md").write_text("# built\n", encoding="utf-8")
    config.RAW_DIR.mkdir(parents=True)
    (config.RAW_DIR / "a.md").write_text("a\n", encoding="utf-8")
    config.CACHE_FILE.write_text("{}", encoding="utf-8")
    purpose = tmp_path / "purpose_demo.md"
    purpose.write_text("# 목적\n", encoding="utf-8")
    cli._snapshot(config, "demo", "built")

    # A fresh clone: only the snapshot exists.
    for path in [tmp_path / "wiki_output", tmp_path / "raw"]:
        cli.shutil.rmtree(path)
    config.CACHE_FILE.unlink()
    purpose.unlink()
    cli.cmd_restore(args)

    assert (config.WIKI_DIR / "index.md").read_text(encoding="utf-8") == "# built\n"
    assert (config.RAW_DIR / "a.md").exists()
    assert config.CACHE_FILE.read_text(encoding="utf-8") == "{}"
    assert purpose.read_text(encoding="utf-8") == "# 목적\n"
