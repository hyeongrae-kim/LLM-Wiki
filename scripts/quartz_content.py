#!/usr/bin/env python3
"""Give every page of the Quartz content copy a readable title (used by scripts/quartz.sh).

Quartz titles a page by its frontmatter `title`, else by its file name
("의안-2206292", "_index"). The wiki itself has no `title` keys, so the copy in
.quartz/content gets one from the first `# heading`; the wiki is not modified.
"""

import re
import sys
from pathlib import Path

SPECIAL = {"index.md": None, "error-book.md": "Error Book", "log.md": "작업 로그 (log.md)"}

content, site_title = Path(sys.argv[1]), sys.argv[2]
for md in content.rglob("*.md"):
    text = md.read_text(encoding="utf-8")
    if md.name == "_index.md":
        title = f"{md.parent.name} 목록"
    elif md.name in SPECIAL and md.parent == content:
        title = SPECIAL[md.name] or site_title
    else:
        m = re.search(r"^# (.+)$", text, re.MULTILINE)
        if not m:
            continue
        title = m.group(1).strip()
    title_line = 'title: "' + title.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end == -1 or re.search(r"^title:", text[4:end], re.MULTILINE):
            continue
        text = "---\n" + title_line + "\n" + text[4:]
    else:
        text = f"---\n{title_line}\n---\n\n{text}"
    md.write_text(text, encoding="utf-8")
