import bench_error_book as eb


def test_open_inject_verify_close(wiki):
    eb.record_lint_issues({"missing_summary": ["members/조국"]})
    [entry] = eb.load_error_book()
    assert entry["status"] == "open" and entry["category"] == "missing_summary"
    assert entry["constraint"] in eb.get_active_constraints()

    eb.record_lint_issues({})                      # 1st clean check
    entry = eb.load_error_book()[0]
    assert entry["status"] == "open" and entry["pass_count"] == 1
    assert all(s["fixed"] for s in entry["samples"])

    eb.record_lint_issues({})                      # 2nd clean check → closed
    entry = eb.load_error_book()[0]
    assert entry["status"] == "closed"
    assert eb.get_active_constraints() == ""


def test_reappearance_resets_the_streak(wiki):
    eb.record_lint_issues({"missing_summary": ["members/A"]})
    eb.record_lint_issues({})
    eb.record_lint_issues({"missing_summary": ["members/A"]})
    assert eb.load_error_book()[0]["pass_count"] == 0


def test_broken_link_waits_for_llm_repair_and_dedups(wiki):
    issue = {"broken_links": [{"from": "votes/표결", "to": "members/안철수"}]}
    eb.record_lint_issues(issue)
    eb.record_lint_issues(issue)
    entry = eb.load_error_book()[0]
    assert len(entry["samples"]) == 1                # same target is not counted twice

    eb.record_lint_issues({})
    eb.record_lint_issues({})
    assert eb.load_error_book()[0]["status"] == "open"   # page not created yet

    eb.mark_samples_fixed("broken_link", ["members/안철수"])
    eb.record_lint_issues({})
    eb.record_lint_issues({})
    assert eb.load_error_book()[0]["status"] == "closed"


def test_export_markdown_and_log(wiki):
    eb.record_lint_issues({"missing_summary": ["members/조국"]})
    path = eb.export_markdown()
    text = path.read_text(encoding="utf-8")
    assert "한 줄 요약 누락" in text and "Known Issues" in text
    assert "opened (missing_summary)" in (wiki / "log.md").read_text(encoding="utf-8")
