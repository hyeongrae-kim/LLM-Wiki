#!/usr/bin/env python3
"""Prepare the Quartz content copy of a wiki (used by scripts/quartz.sh).

* Titles — Quartz titles a page by its frontmatter `title`, else by its file
  name ("의안-2206292", "_index"). The wiki has no `title` keys, so each page
  gets one from its first `# heading`.
* Folder-relative links — the code-written `_index.md` files link their pages
  by bare name (`[[의안-2207608]]`, `[x](digests/_index.md)`), which Obsidian
  resolves but Quartz's absolute link resolution sends to the site root. Such
  links are rewritten to `[[bills/의안-2207608]]` when the target sits next to
  the page.
* Catalogs — the `- **bills/**` entries of index.md and the `_index.md` files
  become links to the folder pages, so the home page has graph edges.

Only the copy in .quartz/content is changed; the wiki itself is not modified.
"""

import re
import sys
from pathlib import Path

SPECIAL = {"index.md": None, "error-book.md": "Error Book", "log.md": "작업 로그 (log.md)"}
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)([^\]]*)\]\]")
MDLINK_RE = re.compile(r"\]\(([^)#\s:]+\.md)\)")
CATALOG_RE = re.compile(r"^- \*\*([^*/]+)/\*\*", re.MULTILINE)


def _exists(content: Path, target: str) -> bool:
    target = target.strip().rstrip("/")
    return bool(target) and ((content / f"{target}.md").is_file() or (content / target).is_dir())


def relink(text: str, content: Path, folder: str) -> str:
    """Prefix bare [[name]] / [x](name.md) links with the page's folder when only that resolves."""
    def _local(target: str) -> str | None:
        target = target.strip().removesuffix(".md")
        if not folder or _exists(content, target) or not _exists(content, f"{folder}/{target}"):
            return None
        return f"{folder}/{target}"

    def _wiki(m: re.Match) -> str:
        local = _local(m.group(1))
        if not local:
            return m.group(0)
        label = "" if "|" in m.group(2) else "|" + m.group(1).strip()   # keep the short label
        return f"[[{local}{m.group(2)}{label}]]"

    def _md(m: re.Match) -> str:
        local = _local(m.group(1))
        return f"]({local}.md)" if local else m.group(0)

    def _catalog(m: re.Match) -> str:
        target = f"{folder}/{m.group(1)}" if folder else m.group(1)
        return f"- [[{target}/_index|{m.group(1)}/]]" if _exists(content, target) else m.group(0)

    text = MDLINK_RE.sub(_md, WIKILINK_RE.sub(_wiki, text))
    return CATALOG_RE.sub(_catalog, text)


def main(content: Path, site_title: str) -> None:
    for md in content.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        folder = md.parent.relative_to(content).as_posix()
        text = relink(text, content, "" if folder == "." else folder)
        if md.name == "_index.md":
            title = f"{md.parent.name} 목록"
        elif md.name in SPECIAL and md.parent == content:
            title = SPECIAL[md.name] or site_title
        else:
            m = re.search(r"^# (.+)$", text, re.MULTILINE)
            title = m.group(1).strip() if m else None
        if title:
            title_line = 'title: "' + title.replace("\\", "\\\\").replace('"', '\\"') + '"'
            if not text.startswith("---\n"):
                text = f"---\n{title_line}\n---\n\n{text}"
            else:
                end = text.find("\n---", 4)
                if end != -1 and not re.search(r"^title:", text[4:end], re.MULTILINE):
                    text = "---\n" + title_line + "\n" + text[4:]
        md.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
