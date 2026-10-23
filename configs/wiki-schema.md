# Wiki Schema — Structured Knowledge Base

> This file is pasted into the ingestion prompt. Section headings, frontmatter
> keys and directory names below are checked by code (lint / repair) and must
> be written exactly as shown, in English. Everything else follows the output
> language of the wiki.

## Directory layout

Page types are declared in `wiki/page_types.yaml`. On first ingestion the LLM
analyses a sample of source articles and proposes a per-corpus directory
schema; you can also set it manually.

**Fixed infrastructure directories (maintained by code):**

```
wiki/
├── sources/               # source-page root
│   ├── digests/           #   structured summaries of source documents
│   └── articles/          #   verbatim copies of the original source text
├── index.md               # directory catalog + knowledge overview (code)
├── log.md                 # append-only operation log (code)
├── error-book.md          # error book rendered for humans (code)
└── page_types.yaml        # registry of page types
```

**Dynamic page-type directories** (defined in `page_types.yaml`, one set per
corpus, English lowercase names such as `entities/`, `events/`, `concepts/`).
Every directory has an `_index.md` that is maintained by code — never write it.

## Frontmatter

```yaml
---
type: source|{dynamic_type}
aliases: [list of aliases / variant names]
tags: [list of tags]
---
```

- `type` equals the directory name (`source` for digests).
- `aliases` is used at retrieval time — list abbreviations, former names,
  foreign-language / hanja names and alternative spellings.
- `created` and `updated` are injected by the engine; do not emit them.

### Knowledge-page template (`{dir}/`)

```markdown
---
type: {dir}
aliases: [aliases]
tags: [tags]
---

# Page title
> One-sentence summary (required, directly under the title)

## Key Facts
- Fact 1 (use full noun phrases — avoid pronouns)
- Fact 2
(required, ≥2)

## Related Pages
- [[dir/page]] — relationship description
(required, ≥2, every item has a [[link]])

## Related Sources
- [[sources/digests/digest-name]] — what this source contributes
```

Optional extra sections (e.g. a timeline) may follow `## Key Facts`.

### Source-digest template (`sources/digests/`)

All four sections are **mandatory**, even for a short source.

```markdown
---
type: source
source_article: <article stem given in the prompt>
tags: [tags]
---

# Source title
> Source: {origin}

## Summary
A short structured summary. (required)

## Key Facts
- Fact 1
- Fact 2
(required, ≥2)

## Key Entities
- Entity name (plain text, no [[links]])
(required, ≥1)

## Related Context
- Background that helps connect this source to other pages (required)
```

## Writing style (the wiki is consumed by an LLM for retrieval)

- **Information density first.** Prefer structured fact lists over prose.
- **Use full noun phrases.** Avoid pronouns — they break entity matching.
- **Informative headings** for optional sections.
- **Always declare aliases** in the frontmatter.
- **Link with the directory path.** `[[dir/page]]` for knowledge pages,
  `[[sources/digests/name]]` for digests; links have no `.md` extension.

## Naming conventions

- Knowledge pages: the canonical name of the entity (follow the page-name rule
  given in the task, e.g. official names; disambiguate homonyms).
- Source digests: the article stem given in the prompt.
- Avoid filesystem-unsafe characters: `/` → `-`, `|` → `-`, remove `"`, `#`, `[`, `]`.
