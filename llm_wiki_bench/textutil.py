"""Text helpers for non-English (especially Korean) corpora.

* ``nfc`` / ``safe_filename`` — Unicode-normalized, filesystem-safe page names
  (macOS keeps NFD names from Finder/zip copies; Hangul is 3 bytes per syllable,
  so names are capped in bytes, not characters).
* ``search_tokens`` — BM25 tokens: ASCII words plus Hangul character bigrams.
* ``word_variants`` — a query word with trailing punctuation / Korean particles
  removed ("조국혁신당은?" → "조국혁신당").
* ``contains_name`` — substring test that does not let a short Hangul name
  match inside a longer word (조국 vs 조국혁신당).
* ``normalize_headings`` — maps Korean / wrong-case section headings that the
  LLM may emit back to the canonical English headings the lint checks expect.
"""

from __future__ import annotations

import re
import unicodedata

_HANGUL = "가-힣"
_HANGUL_RE = re.compile(f"[{_HANGUL}]")
_TOKEN_RE = re.compile(f"[a-z0-9]+|[{_HANGUL}]+")

_UNSAFE_FILENAME_RE = re.compile(r'[\\/|]')
_DROP_FILENAME_RE = re.compile(r'[#"*?<>:\[\]\x00-\x1f​-‍﻿]')

# Longest first so that "에서는" is stripped before "는".
_PARTICLES = sorted(
    ["은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "로", "으로", "도",
     "만", "에서", "에게", "까지", "부터", "보다", "처럼", "이나", "라는", "이라는",
     "에는", "에도", "에서는", "으로는", "과의", "와의", "께서", "이고", "이며"],
    key=len, reverse=True,
)
_PARTICLE_STARTS = "은는이가을를의에와과로도만께"
_EDGE_PUNCT = "?!.,;:\"'()[]{}<>「」『』“”‘’·ㆍ…~"


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def truncate_bytes(text: str, max_bytes: int) -> str:
    """Cut ``text`` to at most ``max_bytes`` UTF-8 bytes on a character boundary."""
    data = text.encode("utf-8")
    if len(data) <= max_bytes:
        return text
    return data[:max_bytes].decode("utf-8", errors="ignore")


def safe_filename(stem: str, max_bytes: int = 200) -> str:
    """Make a page stem safe for every filesystem and for ``[[wikilinks]]``."""
    stem = nfc(stem)
    stem = _UNSAFE_FILENAME_RE.sub("-", stem)
    stem = _DROP_FILENAME_RE.sub("", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = truncate_bytes(stem, max_bytes).rstrip(" .-")
    return stem


def has_hangul(text: str) -> bool:
    return bool(_HANGUL_RE.search(text or ""))


def search_tokens(text: str) -> list[str]:
    """Tokenize for BM25: ASCII words (≥2 chars) and Hangul bigrams."""
    tokens: list[str] = []
    for m in _TOKEN_RE.finditer(nfc(text).lower()):
        tok = m.group()
        if _HANGUL_RE.match(tok):
            if len(tok) == 1:
                continue
            tokens.extend(tok[i:i + 2] for i in range(len(tok) - 1))
        elif len(tok) >= 2:
            tokens.append(tok)
    return tokens


def strip_particles(word: str) -> str:
    """Remove one trailing Korean particle, keeping at least two syllables."""
    for p in _PARTICLES:
        if word.endswith(p) and len(word) - len(p) >= 2 and has_hangul(word[-len(p) - 1]):
            return word[: -len(p)]
    return word


def word_variants(word: str) -> list[str]:
    """The query word, plus its punctuation- and particle-stripped forms."""
    w = nfc(word).strip(_EDGE_PUNCT)
    variants = [w] if w else []
    stripped = strip_particles(w)
    if stripped and stripped not in variants:
        variants.append(stripped)
    return variants


def contains_name(text: str, name: str) -> bool:
    """``name in text``, but a short Hangul name must stand alone or be followed
    by a particle (so 조국 does not match 조국혁신당 and 허영 not 허영심)."""
    if not name:
        return False
    if not has_hangul(name) or len(name) > 2:
        return name in text
    start = 0
    while True:
        i = text.find(name, start)
        if i == -1:
            return False
        before = text[i - 1] if i > 0 else ""
        after = text[i + len(name)] if i + len(name) < len(text) else ""
        if not has_hangul(before) and (not has_hangul(after) or after in _PARTICLE_STARTS):
            return True
        start = i + 1


# ─── Section headings ─────────────────────────────────────────────────────

_CANONICAL_HEADINGS = {
    "Summary": ["summary", "요약", "개요 요약", "요약 정보"],
    "Key Facts": ["key facts", "core facts", "핵심 사실", "주요 사실", "핵심 사실들", "사실", "핵심 정보"],
    "Key Entities": ["key entities", "mentioned entities", "주요 개체", "주요 엔티티", "핵심 개체",
                     "언급된 개체", "등장 개체", "주요 인물 및 기관", "주요 인물", "관련 개체"],
    "Related Context": ["related context", "관련 맥락", "관련 배경", "배경", "맥락", "배경 정보"],
    "Related Pages": ["related pages", "관련 페이지", "관련 문서", "연관 페이지"],
    "Related Sources": ["related sources", "관련 출처", "출처", "관련 자료", "관련 소스", "참고 출처"],
}
_HEADING_LOOKUP = {alias: canon for canon, aliases in _CANONICAL_HEADINGS.items() for alias in aliases}
_H2_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)


def _canonical_heading(title: str) -> str | None:
    key = nfc(title).strip().strip("*").strip().lower()
    if key in _HEADING_LOOKUP:
        return _HEADING_LOOKUP[key]
    # "Key Facts (핵심 사실)" / "핵심 사실 (Key Facts)"
    for canon in _CANONICAL_HEADINGS:
        c = canon.lower()
        if key.startswith(c + " (") or key.startswith(c + "(") or key.endswith(f"({c})"):
            return canon
    return None


def normalize_headings(markdown: str) -> str:
    """Rewrite known ``##`` section headings to their canonical English form."""
    def _sub(m: re.Match) -> str:
        canon = _canonical_heading(m.group(1))
        return f"## {canon}" if canon else m.group(0)
    return _H2_RE.sub(_sub, markdown)
