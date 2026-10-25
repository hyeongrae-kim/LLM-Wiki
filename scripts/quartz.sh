#!/usr/bin/env bash
# Publish the compiled wiki with Quartz 5 (https://quartz.jzhao.xyz).
#
#   scripts/quartz.sh serve [corpus]   live preview on http://localhost:${QUARTZ_PORT:-8080}
#   scripts/quartz.sh build [corpus]   static site in .quartz/public
#
# Quartz is cloned once into .quartz/ (git-ignored) and re-installed when
# QUARTZ_REF changes. Requires Node >= 22 and npm >= 10.9.2. Overrides:
# QUARTZ_REF, QUARTZ_BASE_URL, QUARTZ_TITLE, QUARTZ_CNAME (set only when
# serving from a custom domain).
#
# QUARTZ_REF is a commit of the v5 branch after the plugin 1.0 release: the
# v5.0.0 tag ships explorer/graph/search plugins that fetch
# /static/contentIndex.json and build links from the domain root, so on a
# project site (<user>.github.io/<repo>/) the graph is empty and the explorer
# and search links 404.
set -euo pipefail

ACTION=${1:-serve}
CORPUS=${2:-${WIKI_CORPUS:-assembly_spc}}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WIKI="$ROOT/wiki_output/$CORPUS/wiki"
QZ="$ROOT/.quartz"
QUARTZ_REF=${QUARTZ_REF:-97a2d05f80c4c50534959b1d0d41cc4b3895625e}   # v5 branch, 2026-09-20
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3

[ -d "$WIKI" ] || { echo "❌ No wiki at $WIKI — run 'make build' first"; exit 1; }

node_major=$(node -v 2>/dev/null | sed -E 's/^v([0-9]+).*/\1/' || echo 0)
[ "${node_major:-0}" -ge 22 ] || { echo "❌ Node >= 22 required (found $(node -v 2>/dev/null || echo none))"; exit 1; }
npm_ver=$(npm -v)
if [ "$(printf '%s\n10.9.2\n' "$npm_ver" | sort -V | head -1)" != "10.9.2" ]; then
  echo "❌ npm >= 10.9.2 required (found $npm_ver). Run: npm install -g npm@latest"; exit 1
fi

# Default base URL: <owner>.github.io/<repo> from the origin remote.
if [ -z "${QUARTZ_BASE_URL:-}" ]; then
  slug=$(git -C "$ROOT" remote get-url origin 2>/dev/null | sed -E 's#(git@|https://)github.com[:/]##; s#\.git$##')
  QUARTZ_BASE_URL="${slug%%/*}.github.io/${slug##*/}"
fi

# .quartz/ holds only generated files (config, content copy, build output).
if [ -d "$QZ" ] && [ "$(cat "$QZ/.quartz-ref" 2>/dev/null)" != "$QUARTZ_REF" ]; then
  echo "♻️  Quartz version changed → reinstalling .quartz/"
  rm -rf "$QZ"
fi
if [ ! -d "$QZ" ]; then
  echo "⬇️  Installing Quartz $QUARTZ_REF into .quartz/ ..."
  git init -q "$QZ"
  git -C "$QZ" fetch -q --depth 1 https://github.com/jackyzha0/quartz.git "$QUARTZ_REF"
  git -C "$QZ" checkout -q FETCH_HEAD
  (cd "$QZ" && npm ci --no-audit --no-fund)
  echo "$QUARTZ_REF" > "$QZ/.quartz-ref"
fi
if [ ! -f "$QZ/quartz.config.yaml" ]; then
  (cd "$QZ" && npx quartz create -t default -X new -l absolute -b "$QUARTZ_BASE_URL")
fi

# Site title, Korean locale, base URL, absolute [[dir/page]] links.
QUARTZ_BASE_URL="$QUARTZ_BASE_URL" "$PY" "$ROOT/scripts/quartz_config.py" "$QZ/quartz.config.yaml" "$CORPUS"

if [ ! -f "$QZ/.plugins-installed" ]; then
  # Plugins come from npm (package.json); this adds any enabled in the config but missing.
  (cd "$QZ" && npx quartz plugin install --from-config) || exit 1
  touch "$QZ/.plugins-installed"
fi

# Wiki → content/ (Markdown only; yaml/jsonl bookkeeping files are skipped).
rm -rf "$QZ/content"
mkdir -p "$QZ/content"
rsync -a --exclude '*.yaml' --exclude '*.jsonl' --exclude '.DS_Store' "$WIKI/" "$QZ/content/"
"$PY" "$ROOT/scripts/quartz_content.py" "$QZ/content" "${QUARTZ_TITLE:-LLM-Wiki · $CORPUS}"

cd "$QZ"
if [ "$ACTION" = "serve" ]; then
  npx quartz build --serve --port "${QUARTZ_PORT:-8080}"
else
  npx quartz build
  echo "✅ Site built: $QZ/public"
fi
