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


def test_unlink_missing_keeps_existing_and_sources():
    text = "- [[bills/법안]] / [[members/조국]] / [[sources/digests/x]] / [[parties/정당|정당들]]"
    out = bench_ingest._unlink_missing(text, {"members/조국", "조국"})
    assert out == "- 법안 / [[members/조국]] / [[sources/digests/x]] / 정당들"


def test_grounding_uses_original_articles(wiki):
    (wiki / "sources" / "digests").mkdir(parents=True)
    (wiki / "sources" / "articles").mkdir(parents=True)
    (wiki / "sources" / "digests" / "d1.md").write_text("---\nsource_article: a1\n---\n요약", encoding="utf-8")
    (wiki / "sources" / "articles" / "a1.md").write_text("원문 전체 텍스트", encoding="utf-8")
    page = "# p\n## Key Facts\n- x\n## Related Sources\n- [[sources/digests/d1]] — d\n"
    srcs = bench_ingest._grounding_sources(page, page.split("\n"), wiki / "sources" / "digests")
    assert srcs == ["원문 전체 텍스트"]
