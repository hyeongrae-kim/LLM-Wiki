import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "quartz_content", Path(__file__).resolve().parent.parent / "scripts" / "quartz_content.py")
qc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qc)


def _site(tmp_path):
    for rel in ["index.md", "bills/_index.md", "bills/의안-1.md", "members/김용민.md",
                "sources/_index.md", "sources/digests/_index.md"]:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("# t\n", encoding="utf-8")
    return tmp_path


def test_bare_links_in_folder_index_get_the_folder(tmp_path):
    site = _site(tmp_path)
    text = "- [[의안-1]] x\n- [[의안-1|첫 법안]]\n- [[members/김용민]]\n- [[없는-페이지]]"
    assert qc.relink(text, site, "bills").splitlines() == [
        "- [[bills/의안-1|의안-1]] x",
        "- [[bills/의안-1|첫 법안]]",
        "- [[members/김용민]]",          # already resolves from the root
        "- [[없는-페이지]]",             # resolves nowhere: left alone
    ]


def test_markdown_links_and_catalogs(tmp_path):
    site = _site(tmp_path)
    out = qc.relink("- **digests/** (3 pages)\nSee [d](digests/_index.md).", site, "sources")
    assert out == "- [[sources/digests/_index|digests/]] (3 pages)\nSee [d](sources/digests/_index.md)."
    assert qc.relink("- **bills/** (1 pages)\n- **nope/** (0 pages)", site, "") == \
        "- [[bills/_index|bills/]] (1 pages)\n- **nope/** (0 pages)"
