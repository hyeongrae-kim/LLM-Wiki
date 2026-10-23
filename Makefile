# LLM-Wiki — one-line shortcuts for the Korean demo (22대 국회 특별검사법).
# Run `make help` for the list. Variables can be overridden: make build CORPUS=foo

PY       ?= python3
VENV     ?= .venv
CORPUS   ?= assembly_spc
EXAMPLES ?= examples/assembly_spc
CONFIG   ?= corpora/assembly
PRESET   ?= full
RAW      ?= raw
PORT     ?= 8080
TITLE    ?= LLM-Wiki · 22대 국회 특별검사법
Q        ?= 순직 해병 특검법 첫 본회의 표결에서 국민의힘 소속으로 찬성한 의원은?

BIN := $(VENV)/bin
CLI := $(BIN)/llm-wiki
C   := --corpus $(CORPUS)

.PHONY: help setup convert prepare build quickstart status search ask eval \
        demo-add demo-errorbook demo-fix demo-reset test site deploy-pages

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-16s %s\n", $$1, $$2}'

setup:  ## Create .venv, install the package (editable) and copy .env.example → .env
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -q -e '.[dev]'
	@test -f .env || (cp .env.example .env && echo "→ .env created: set OPENAI_API_KEY")

convert:  ## (Optional) regenerate example articles from raw/ tables
	$(BIN)/python corpora/assembly/convert.py --raw $(RAW) --out $(EXAMPLES)

prepare:  ## Copy example articles + purpose/page types into place (PRESET=small|full)
	$(CLI) prepare $(C) --source $(EXAMPLES) --config-dir $(CONFIG) --preset $(PRESET)

build:  ## Compile the wiki, then save the "built" snapshot used by demo-reset
	$(CLI) build $(C)
	$(CLI) errorbook $(C) export
	$(CLI) snapshot $(C) --name built

quickstart:  ## Small end-to-end build (~27 documents)
	$(MAKE) prepare PRESET=small
	$(MAKE) build

status:  ## Wiki statistics
	$(CLI) status $(C)

search:  ## wiki_search only, no LLM (Q="…")
	$(CLI) search $(C) "$(Q)"

ask:  ## Ask the Retrieval-as-Reasoning agent (Q="…")
	$(CLI) ask $(C) "$(Q)" -v

eval:  ## Score 10 generated questions (gold answers from the tables)
	$(CLI) eval $(C) --limit 10

demo-add:  ## Live: add the 2026 지방선거 투표용지 특검 documents
	$(CLI) add $(C) $(EXAMPLES)/add/*.md

demo-errorbook:  ## Live: plant 3 defects, lint (record), show injected constraints
	$(CLI) errorbook $(C) inject-demo
	$(CLI) lint $(C)
	$(CLI) errorbook $(C) show

demo-fix:  ## Live: repair (code + LLM), then verify twice so entries close
	$(CLI) fix $(C) --llm
	$(CLI) lint $(C)
	$(CLI) errorbook $(C) export

demo-reset:  ## Restore the wiki to the "built" snapshot
	$(CLI) restore $(C) --name built

test:  ## Offline tests (no API calls)
	$(BIN)/pytest -q

site:  ## Serve the wiki with Quartz on http://localhost:$(PORT) (PORT=8090 if 8080 is taken)
	QUARTZ_PORT=$(PORT) QUARTZ_TITLE="$(TITLE)" scripts/quartz.sh serve $(CORPUS)

deploy-pages:  ## Build the Quartz site and publish it to the gh-pages branch
	QUARTZ_TITLE="$(TITLE)" scripts/deploy_pages.sh $(CORPUS)
