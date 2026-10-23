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


def test_merge_related_sources_keeps_old_provenance():
    old = "# p\n## Key Facts\n- a\n## Related Sources\n- [[sources/digests/의안-1]] — bill\n"
    new = "# p\n## Key Facts\n- a\n- b\n## Related Sources\n- [[sources/digests/표결-9]] — vote\n"
    merged = bench_ingest._merge_related_sources(new, old)
    assert "[[sources/digests/표결-9]]" in merged and "[[sources/digests/의안-1]]" in merged
    assert merged.index("표결-9") < merged.index("의안-1")


def test_resolve_mangled_digest_links(wiki):
    import bench_config as config
    d = wiki / "sources" / "digests"
    d.mkdir(parents=True)
    (d / "표결-1366-2024-12-10-위헌적-비상계엄-선포를-통한-내란-행위의-진상규명을-위한-특별검사의-수사요구안.md").write_text("x", encoding="utf-8")
    page = wiki / "votes" / "p.md"
    page.parent.mkdir()
    page.write_text("- [[sources/digests/표결-1366-2024-12-10-위헌적-비상계엄-선포를-통한-내란-행위의-진상규명을-위한-특별]]\n", encoding="utf-8")
    bench_ingest._resolve_digest_links(page)
    assert "특별검사의-수사요구안]]" in page.read_text(encoding="utf-8")
