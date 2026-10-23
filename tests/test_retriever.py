from conftest import write_page
from wiki_retriever import WikiRetriever


def _wiki(wiki_dir):
    write_page(wiki_dir, "members/조국.md", "# 조국\n> 조국혁신당 대표, 비례대표 의원\n## Key Facts\n- 조국은 비례대표 의원이다\n",
               aliases="曺國, CHO KUK")
    write_page(wiki_dir, "parties/조국혁신당.md", "# 조국혁신당\n> 2024년 창당한 정당\n## Key Facts\n- 순직 해병 특검법에 찬성했다\n")
    write_page(wiki_dir, "bills/순직 해병 특검법.md", "# 순직 해병 특검법\n> 의안 2200038\n## Key Facts\n- 2024-07-04 본회의에서 수정가결\n")
    r = WikiRetriever(wiki_dir)
    r.load()
    return r


def test_particle_query_hits_the_right_page(wiki):
    r = _wiki(wiki)
    assert r.search("조국은", limit=1)[0].page.rel_path == "members/조국.md"
    assert r.search("조국혁신당의", limit=1)[0].page.rel_path == "parties/조국혁신당.md"


def test_hangul_bm25_on_body_text(wiki):
    r = _wiki(wiki)
    paths = [x.page.rel_path for x in r.search("수정가결", limit=3)]
    assert "bills/순직 해병 특검법.md" in paths


def test_read_accepts_wikilink_paths(wiki):
    r = _wiki(wiki)
    out = r.read(["members/조국"])
    assert out[0]["type"] == "file" and out[0]["name"] == "조국"
