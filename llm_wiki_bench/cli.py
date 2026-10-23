"""llm-wiki — command-line front end for building, querying and demoing an LLM-Wiki.

Typical flow (see README.ko.md / docs/DEMO_KO.md):

    llm-wiki prepare --source examples/assembly_spc --config-dir corpora/assembly --preset small
    llm-wiki build                       # compile raw/<corpus>/articles into wiki_output/<corpus>/wiki
    llm-wiki search "순직 해병"           # wiki_search only (no LLM)
    llm-wiki ask "…질문…" -v             # Retrieval-as-Reasoning agent + answer
    llm-wiki add examples/assembly_spc/add/*.md
    llm-wiki lint / fix --llm / errorbook show|export|inject-demo
    llm-wiki snapshot / restore          # make a live demo repeatable

The corpus name defaults to $WIKI_CORPUS (or "assembly_spc"); every command
accepts --corpus. Settings come from the environment or a .env file.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path

_PKG_DIR = Path(__file__).parent
if str(_PKG_DIR) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR))
REPO = _PKG_DIR.parent


# ─── setup ────────────────────────────────────────────────────────────────

def _setup(args):
    """Apply CLI overrides to the environment, then import and activate config."""
    if getattr(args, "lang", None):
        os.environ["WIKI_LANG"] = args.lang
    logging.basicConfig(level=logging.INFO if args.log_llm else logging.WARNING,
                        format="  %(name)s: %(message)s")
    import bench_config as config
    config.set_dataset(args.corpus)
    return config


def _knowledge_pages(config) -> dict[str, list[Path]]:
    out = {}
    for name in config.get_page_types():
        d = config.WIKI_DIR / name
        if d.is_dir():
            out[name] = sorted(p for p in d.glob("*.md") if p.name != "_index.md")
    return out


def _print_status(config) -> None:
    import bench_error_book as eb
    pages = _knowledge_pages(config)
    digests = config.WIKI_DIR / "sources" / "digests"
    n_digests = len([p for p in digests.glob("*.md") if p.name != "_index.md"]) if digests.is_dir() else 0
    errors = eb.load_error_book()
    n_open = sum(1 for e in errors if e.get("status") != "closed")
    print(f"\n📚 Wiki: {config.WIKI_DIR}")
    print(f"   knowledge pages: {sum(len(v) for v in pages.values())} "
          f"({', '.join(f'{k} {len(v)}' for k, v in pages.items() if v)})")
    print(f"   source digests : {n_digests}")
    print(f"   error book     : {n_open} open / {len(errors) - n_open} closed")


# ─── prepare / build / add ────────────────────────────────────────────────

def cmd_prepare(args) -> None:
    config = _setup(args)
    src = Path(args.source)
    cfg = Path(args.config_dir) if args.config_dir else None

    if cfg:
        purpose_dst = config.BASE_DIR / f"purpose_{args.corpus}.md"
        if (cfg / "purpose.md").exists() and (args.force or not purpose_dst.exists()):
            shutil.copyfile(cfg / "purpose.md", purpose_dst)
            print(f"  purpose     → {purpose_dst.relative_to(REPO)}")
        types_dst = config.WIKI_DIR / "page_types.yaml"
        if (cfg / "page_types.yaml").exists() and (args.force or not types_dst.exists()):
            shutil.copyfile(cfg / "page_types.yaml", types_dst)
            print(f"  page types  → {types_dst.relative_to(REPO)}")

    articles_dir = src / "articles" if (src / "articles").is_dir() else src
    manifest = src / "manifest.json"
    if args.preset and manifest.exists():
        names = json.loads(manifest.read_text(encoding="utf-8"))[args.preset]
        files = [articles_dir / n for n in names]
    else:
        files = sorted(articles_dir.glob("*.md"))
    if not files:
        sys.exit(f"❌ No articles found in {articles_dir}")

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in files:
        dst = config.RAW_DIR / f.name
        if not dst.exists() or dst.read_bytes() != f.read_bytes():
            shutil.copyfile(f, dst)
            copied += 1
    config.ensure_wiki_dirs()
    total = len(list(config.RAW_DIR.glob("*.md")))
    print(f"  articles    → {config.RAW_DIR.relative_to(REPO)} ({copied} copied, {total} total)")
    print(f"\nNext: llm-wiki build --corpus {args.corpus}")


def cmd_build(args) -> None:
    config = _setup(args)
    import bench_ingest
    paths = sorted(config.RAW_DIR.glob("*.md")) if config.RAW_DIR.exists() else []
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        sys.exit(f"❌ No articles in {config.RAW_DIR}. Run `llm-wiki prepare` first.")
    t0 = time.time()
    bench_ingest.ingest_batch(paths, batch_size=args.batch_size, force=args.force, finalize=args.finalize)
    print(f"\n⏱  build took {time.time() - t0:.0f}s")
    _print_status(config)


def cmd_add(args) -> None:
    config = _setup(args)
    import bench_ingest
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    targets = []
    for f in map(Path, args.files):
        if not f.is_file():
            sys.exit(f"❌ Not a file: {f}")
        dst = config.RAW_DIR / f.name
        shutil.copyfile(f, dst)
        targets.append(dst)
    print(f"📥 Adding {len(targets)} document(s) to {config.RAW_DIR.relative_to(REPO)}")
    bench_ingest.ingest_batch(targets, batch_size=args.batch_size, finalize=args.finalize)
    _print_status(config)


# ─── search / ask / eval ──────────────────────────────────────────────────

def _retriever(config):
    from wiki_retriever import WikiRetriever
    r = WikiRetriever(config.WIKI_DIR)
    r.load()
    if not r.pages:
        sys.exit(f"❌ Empty wiki: {config.WIKI_DIR}. Run `llm-wiki build` first.")
    return r


def cmd_search(args) -> None:
    config = _setup(args)
    results = _retriever(config).search(args.query, limit=args.k)
    print(f'\n🔎 wiki_search("{args.query}") → {len(results)} result(s)\n')
    for i, res in enumerate(results, 1):
        print(f"{i:>2}. [{res.score:6.1f}] {res.page.rel_path}  ({', '.join(res.matched_fields)})")
        if res.page.description:
            print(f"     {res.page.description[:100]}")


def _ask(config, retriever, question: str, args):
    from llm_client import call_llm_with_tools
    from wiki_agent import WikiAgent
    import run_qa
    agent = WikiAgent(
        retriever,
        call_llm_with_tools=call_llm_with_tools,
        model=args.model or config.LLM_PREMIUM_MODEL,
        t_max=args.t_max,
        patience=args.patience,
        select_pages=args.select_pages,
        verbose=args.verbose,
    )
    rr = agent.retrieve(question)
    answer = run_qa._answer(question, run_qa._format_context(rr.pages, rr.pages_text),
                            model=args.answer_model)
    return rr, answer


def cmd_ask(args) -> None:
    config = _setup(args)
    retriever = _retriever(config)
    print(f"\n❓ {args.question}\n")
    rr, answer = _ask(config, retriever, args.question, args)
    print("\n🧭 Retrieval trace")
    for i, step in enumerate(rr.trace, 1):
        print(f"   {i:>2}. {step}")
    print(f"\n📄 Evidence pages ({len(rr.pages)}): " + ", ".join(p for p, _ in rr.pages))
    print(f"🔧 Tool calls: {rr.total_calls}")
    print(f"\n💬 {answer}\n")


def _norm(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text or "").lower()


def _char_f1(pred: str, gold: str) -> float:
    from collections import Counter
    p, g = Counter(_norm(pred)), Counter(_norm(gold))
    overlap = sum((p & g).values())
    if not overlap:
        return 0.0
    precision, recall = overlap / sum(p.values()), overlap / sum(g.values())
    return 2 * precision * recall / (precision + recall)


def cmd_eval(args) -> None:
    config = _setup(args)
    qpath = Path(args.questions or REPO / "examples" / args.corpus / "questions.jsonl")
    questions = [json.loads(line) for line in qpath.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.stage != "all":
        questions = [q for q in questions if q.get("stage") == args.stage]
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    if args.limit and len(questions) > args.limit:
        step = len(questions) / args.limit          # spread over question types
        questions = [questions[int(i * step)] for i in range(args.limit)]
    retriever = _retriever(config)
    out_dir = REPO / "results" / args.corpus
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"eval-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    hits, f1s = 0, []
    with open(out_path, "w", encoding="utf-8") as f:
        for i, q in enumerate(questions, 1):
            rr, answer = _ask(config, retriever, q["question"], args)
            gold = q["answer"]
            hit = bool(_norm(gold)) and (_norm(gold) in _norm(answer) or _norm(answer) in _norm(gold)) \
                and bool(_norm(answer))
            f1 = _char_f1(answer, gold)
            hits += hit
            f1s.append(f1)
            print(f"[{i}/{len(questions)}] {'✅' if hit else '❌'} {q['id']}: {answer}  (gold: {gold}, "
                  f"{rr.total_calls} calls)")
            f.write(json.dumps({**q, "prediction": answer, "match": hit, "char_f1": round(f1, 3),
                                "trace": rr.trace, "pages": [p for p, _ in rr.pages]},
                               ensure_ascii=False) + "\n")
    if questions:
        print(f"\n📊 match {hits}/{len(questions)} ({hits / len(questions):.0%}) · "
              f"char-F1 {sum(f1s) / len(f1s):.3f} → {out_path.relative_to(REPO)}")


# ─── lint / fix / error book ──────────────────────────────────────────────

def cmd_lint(args) -> None:
    config = _setup(args)
    import bench_ingest
    import bench_error_book as eb
    issues = bench_ingest.quick_lint_bench()
    if not issues:
        print("✅ No lint issues")
    for key, items in issues.items():
        items = items if isinstance(items, list) else [items]
        recorded = "📔" if key in eb.ISSUE_TEMPLATES else "  "
        print(f"{recorded} {key}: {len(items)}")
        for item in items[:3]:
            print(f"      - {str(item)[:110]}")
    eb.export_markdown()
    eb.print_error_book()


def cmd_fix(args) -> None:
    config = _setup(args)
    import bench_ingest
    import bench_error_book as eb
    fixes = bench_ingest.auto_fix_bench()
    print("🔧 Code fixes: " + (", ".join(f"{k}={v}" for k, v in fixes.items() if v) or "none"))
    if args.llm:
        bench_ingest.llm_fix_structural()
        if args.content:
            bench_ingest.llm_fix_content()
        bench_ingest._rebuild_sources_index()
        bench_ingest._rebuild_global_index()
    issues = bench_ingest.quick_lint_bench()
    remaining = sum(len(v) if isinstance(v, list) else 1 for v in issues.values())
    print(f"🔍 Re-lint: {remaining} issue(s) remaining")
    eb.export_markdown()
    eb.print_error_book()


def cmd_errorbook(args) -> None:
    config = _setup(args)
    import bench_error_book as eb
    if args.action == "show":
        eb.print_error_book()
        constraints = eb.get_active_constraints()
        print("Constraints injected into the next Step 2 prompt:\n")
        print(constraints or "(none)")
    elif args.action == "export":
        path = eb.export_markdown()
        print(f"📝 {path}")
    elif args.action == "inject-demo":
        _snapshot(config, args.corpus, "before-inject")
        _inject_demo(config)


_MINORITY_RE = re.compile(r"^- ([가-힣]{2,4}) \(([^)]+)\): (찬성|반대|기권)$", re.MULTILINE)


def _inject_demo(config) -> None:
    """Plant three deterministic defects for a live Error Book demonstration."""
    wiki = config.WIKI_DIR
    pages = _knowledge_pages(config)
    all_stems = {p.stem for ps in pages.values() for p in ps}
    all_text = {p: p.read_text(encoding="utf-8") for ps in pages.values() for p in ps}
    aliases = set()
    for text in all_text.values():
        m = re.search(r"^aliases:\s*\[(.*)\]", text, re.MULTILINE)
        if m:
            aliases |= {a.strip().strip("'\"") for a in m.group(1).split(",")}
    used: set[Path] = set()

    # (1) broken link to a real member that has no page yet (from vote articles).
    articles = sorted((wiki / "sources" / "articles").glob("vote-*.md")) or \
        sorted((wiki / "sources" / "articles").glob("*.md"))
    name = None
    for art in articles:
        for m in _MINORITY_RE.finditer(art.read_text(encoding="utf-8")):
            if m.group(1) not in all_stems and m.group(1) not in aliases:
                name = m.group(1)
                break
        if name:
            break
    if name:
        host = next((p for p, t in all_text.items() if name in t and "## Key Facts" in t), None) or \
            next((p for p, t in all_text.items() if "## Key Facts" in t), None)
        text = all_text[host]
        text = text.replace("## Key Facts\n", f"## Key Facts\n- {name} 의원도 관련 표결에 참여했다 ([[members/{name}]])\n", 1)
        host.write_text(text, encoding="utf-8")
        used.add(host)
        print(f"  ① broken link   : [[members/{name}]] added to {host.relative_to(wiki)} (no such page yet)")
    else:
        print("  ① broken link   : skipped (no member without a page found)")

    # (2) delete the one-line summary of a member page.
    for p in pages.get("members", []) + [p for ps in pages.values() for p in ps]:
        if p in used:
            continue
        text = p.read_text(encoding="utf-8")
        new = re.sub(r"(^# [^\n]+\n)(?:\s*\n)*> [^\n]*\n", r"\1", text, count=1, flags=re.MULTILINE)
        if new != text:
            p.write_text(new, encoding="utf-8")
            used.add(p)
            print(f"  ② missing summary: removed the '> …' line of {p.relative_to(wiki)}")
            break

    # (3) move a bill page into the wrong directory (its `type` stays correct).
    src_dir = "bills" if pages.get("bills") else next(iter(pages))
    wrong_dir = next((d for d in pages if d != src_dir and (wiki / d).is_dir()), None)
    victim = next((p for p in pages.get(src_dir, []) if p not in used), None)
    if victim and wrong_dir:
        dst = wiki / wrong_dir / victim.name
        shutil.move(str(victim), dst)
        print(f"  ③ wrong directory: moved {src_dir}/{victim.name} → {wrong_dir}/ (type: {src_dir})")

    print("\nNext: `llm-wiki lint` (record) → `llm-wiki errorbook show` (constraints) → "
          "`llm-wiki add …` or `llm-wiki fix --llm` (repair) → `llm-wiki lint` ×2 (verify → close)")
    print("Undo: `llm-wiki restore --name before-inject`")


# ─── snapshot / restore / status ──────────────────────────────────────────

def _snapshot_dir(corpus: str, name: str) -> Path:
    return REPO / ".snapshots" / corpus / name


def _snapshot(config, corpus: str, name: str) -> None:
    dst = _snapshot_dir(corpus, name)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    shutil.copytree(config.WIKI_DIR, dst / "wiki")
    if config.RAW_DIR.exists():
        shutil.copytree(config.RAW_DIR, dst / "articles")
    if config.CACHE_FILE.exists():
        shutil.copyfile(config.CACHE_FILE, dst / "cache.json")
    print(f"📸 Snapshot saved: {dst.relative_to(REPO)}")


def cmd_snapshot(args) -> None:
    config = _setup(args)
    _snapshot(config, args.corpus, args.name)


def cmd_restore(args) -> None:
    config = _setup(args)
    src = _snapshot_dir(args.corpus, args.name)
    if not (src / "wiki").exists():
        sys.exit(f"❌ No snapshot at {src}")
    shutil.rmtree(config.WIKI_DIR, ignore_errors=True)
    shutil.copytree(src / "wiki", config.WIKI_DIR)
    if (src / "articles").exists():
        shutil.rmtree(config.RAW_DIR, ignore_errors=True)
        shutil.copytree(src / "articles", config.RAW_DIR)
    if (src / "cache.json").exists():
        shutil.copyfile(src / "cache.json", config.CACHE_FILE)
    print(f"♻️  Restored {config.WIKI_DIR.relative_to(REPO)} from {src.relative_to(REPO)}")


def cmd_status(args) -> None:
    config = _setup(args)
    _print_status(config)


# ─── argument parsing ─────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--corpus", default=os.environ.get("WIKI_CORPUS", "assembly_spc"),
                        help="Corpus name: raw/<corpus>/articles → wiki_output/<corpus>/wiki")
    common.add_argument("--lang", choices=["en", "ko"], help="Override WIKI_LANG")
    common.add_argument("--log-llm", action="store_true", help="Log every LLM call (model, size, latency)")

    agent_opts = argparse.ArgumentParser(add_help=False)
    agent_opts.add_argument("-v", "--verbose", action="store_true", help="Print every tool call")
    agent_opts.add_argument("--model", help="Retrieval agent model (default: LLM_PREMIUM_MODEL)")
    agent_opts.add_argument("--answer-model", help="Answer model (default: LLM_FAST_MODEL)")
    agent_opts.add_argument("--t-max", type=int, default=15, help="Tool-call budget (paper: 15)")
    agent_opts.add_argument("--patience", type=int, default=3, help="Consecutive empty searches (paper: 3)")
    agent_opts.add_argument("--select-pages", type=int, default=5, help="Pages per search (paper: 5)")

    ap = argparse.ArgumentParser(prog="llm-wiki", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", parents=[common], help="Copy example articles + corpus config into place")
    p.add_argument("--source", default="examples/assembly_spc", help="Directory with articles/ (+ manifest.json)")
    p.add_argument("--config-dir", default="corpora/assembly", help="Directory with purpose.md / page_types.yaml")
    p.add_argument("--preset", choices=["small", "full"], help="Subset listed in manifest.json")
    p.add_argument("--force", action="store_true", help="Overwrite existing purpose / page types")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("build", parents=[common], help="Compile raw/<corpus>/articles into the wiki")
    p.add_argument("--batch-size", type=int, default=2, help="Articles per LLM call (default 2)")
    p.add_argument("--limit", type=int, help="Only the first N articles")
    p.add_argument("--force", action="store_true", help="Re-ingest cached articles")
    p.add_argument("--finalize", choices=["full", "light", "none"], default="full")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("add", parents=[common], help="Add new documents to an existing wiki")
    p.add_argument("files", nargs="+")
    p.add_argument("--batch-size", type=int, default=2,
                   help="Articles per LLM call (batch mode fixes digest names to the article stems)")
    p.add_argument("--finalize", choices=["full", "light", "none"], default="light")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("search", parents=[common], help="wiki_search only (no LLM)")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=10)
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("ask", parents=[common, agent_opts], help="Answer a question with the wiki agent")
    p.add_argument("question")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("eval", parents=[common, agent_opts], help="Run questions.jsonl and score answers")
    p.add_argument("--questions", help="Default: examples/<corpus>/questions.jsonl")
    p.add_argument("--stage", choices=["initial", "add", "all"], default="initial")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--ids", help="Comma-separated question ids")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("lint", parents=[common], help="Run the lint and record issues in the Error Book")
    p.set_defaults(func=cmd_lint)

    p = sub.add_parser("fix", parents=[common], help="Code fixes (+ LLM repairs with --llm), then re-lint")
    p.add_argument("--llm", action="store_true", help="Run structural LLM repairs")
    p.add_argument("--content", action="store_true", help="Also run grounding / contradiction checks")
    p.set_defaults(func=cmd_fix)

    p = sub.add_parser("errorbook", parents=[common], help="Show / export the Error Book, or plant demo defects")
    p.add_argument("action", choices=["show", "export", "inject-demo"])
    p.set_defaults(func=cmd_errorbook)

    p = sub.add_parser("snapshot", parents=[common], help="Save wiki + articles + cache")
    p.add_argument("--name", default="latest")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("restore", parents=[common], help="Restore a snapshot")
    p.add_argument("--name", default="latest")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("status", parents=[common], help="Wiki statistics")
    p.set_defaults(func=cmd_status)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
