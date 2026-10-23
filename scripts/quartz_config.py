#!/usr/bin/env python3
"""Adjust a Quartz 5 quartz.config.yaml for an LLM-Wiki (used by scripts/quartz.sh)."""

import os
import sys
from pathlib import Path

import yaml

path, corpus = Path(sys.argv[1]), sys.argv[2]
cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
conf = cfg.setdefault("configuration", {})
conf["pageTitle"] = os.environ.get("QUARTZ_TITLE", f"LLM-Wiki · {corpus}")
conf["locale"] = "ko-KR"
conf["baseUrl"] = os.environ["QUARTZ_BASE_URL"]
conf["analytics"] = None
conf["ignorePatterns"] = sorted(set(conf.get("ignorePatterns") or []) | {".obsidian", "private", "templates"})

repo = "https://github.com/" + os.environ["QUARTZ_BASE_URL"].replace(".github.io/", "/", 1)
for plugin in cfg.get("plugins", []):
    name = plugin.get("source", "").rsplit("/", 1)[-1]
    if name == "crawl-links":            # links are written as [[dir/page]] from the wiki root
        plugin.setdefault("options", {})["markdownLinkResolution"] = "absolute"
    elif name == "footer":
        plugin["options"] = {"links": {
            "GitHub": repo,
            "Paper (arXiv 2605.25480)": "https://arxiv.org/abs/2605.25480",
        }}

path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"⚙️  {path.name}: title={conf['pageTitle']!r} baseUrl={conf['baseUrl']} links=absolute locale=ko-KR")
