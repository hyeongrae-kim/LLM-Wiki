import bench_config as config
import bench_ingest


def test_korean_step2_prompt(wiki, monkeypatch):
    monkeypatch.setattr(config, "get_purpose_file", lambda: config.BASE_DIR / "corpora" / "assembly" / "purpose.md")
    system, user = bench_ingest.build_ingest_prompt_batch(
        [{"title": "의안 2200038 순직 해병 특검법", "content": "본문"}])
    assert "Use English page names" not in user
    assert "Use official Korean names" in user
    assert "Wikipedia" not in user


def test_korean_example_in_single_prompt(wiki, monkeypatch):
    monkeypatch.setattr(config, "get_purpose_file", lambda: config.BASE_DIR / "corpora" / "assembly" / "purpose.md")
    _, user = bench_ingest.build_ingest_prompt("의안 2200038", "", "본문")
    assert "세종대왕" in user and "Einstein" not in user


def test_constraints_reach_the_batch_prompt(wiki, monkeypatch):
    import bench_error_book as eb
    monkeypatch.setattr(config, "get_purpose_file", lambda: config.BASE_DIR / "corpora" / "assembly" / "purpose.md")
    eb.record_lint_issues({"missing_summary": ["members/조국"]})
    _, user = bench_ingest.build_ingest_prompt_batch([{"title": "t", "content": "c"}])
    assert "## Known Issues (must avoid)" in user
