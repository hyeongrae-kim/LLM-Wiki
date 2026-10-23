import unicodedata

import textutil


def test_search_tokens_hangul_bigrams_and_ascii():
    toks = textutil.search_tokens("조국혁신당 BM25 a")
    assert {"조국", "국혁", "혁신", "신당", "bm25"} <= set(toks)
    assert "a" not in toks  # single ASCII characters are dropped


def test_word_variants_strip_particles_and_punctuation():
    assert "조국혁신당" in textutil.word_variants("조국혁신당은?")
    assert "법제사법위원회" in textutil.word_variants("법제사법위원회에서")
    # A name that merely ends in a particle-like syllable keeps its original form.
    assert textutil.word_variants("한병도")[0] == "한병도"


def test_contains_name_respects_short_hangul_names():
    assert not textutil.contains_name("조국혁신당 소속 의원", "조국")
    assert textutil.contains_name("조국은 대표발의했다", "조국")
    assert textutil.contains_name("(조국, 황운하)", "조국")
    assert textutil.contains_name("이재명 대표", "이재명")


def test_safe_filename_nfc_bytes_and_unsafe_chars():
    nfd = unicodedata.normalize("NFD", "법제사법위원회")
    assert textutil.safe_filename(nfd) == "법제사법위원회"
    long = textutil.safe_filename("특" * 150)
    assert len(long.encode("utf-8")) <= 200
    assert textutil.safe_filename('a/b|c#d"e[f]') == "a-b-cdef"


def test_normalize_headings():
    md = "# 제목\n## 요약\n본문\n## key facts\n- a\n## Key Facts (핵심 사실)\n## 관련 페이지\n## 타임라인\n"
    out = textutil.normalize_headings(md)
    assert "## Summary" in out
    assert out.count("## Key Facts") == 2
    assert "## Related Pages" in out
    assert "## 타임라인" in out  # unknown headings are left alone
