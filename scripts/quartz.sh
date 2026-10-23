#!/usr/bin/env bash
# Publish the compiled wiki with Quartz 5 (https://quartz.jzhao.xyz).
#
#   scripts/quartz.sh serve [corpus]   live preview on http://localhost:${QUARTZ_PORT:-8080}
#   scripts/quartz.sh build [corpus]   static site in .quartz/public
#
# Quartz is cloned once into .quartz/ (git-ignored). Requires Node >= 22 and
# npm >= 10.9.2. Overrides: QUARTZ_REF, QUARTZ_BASE_URL, QUARTZ_TITLE,
# QUARTZ_CNAME (set only when serving from a custom domain).
set -euo pipefail

ACTION=${1:-serve}
CORPUS=${2:-${WIKI_CORPUS:-assembly_spc}}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
WIKI="$ROOT/wiki_output/$CORPUS/wiki"
QZ="$ROOT/.quartz"
QUARTZ_REF=${QUARTZ_REF:-v5.0.0}
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

if [ ! -d "$QZ" ]; then
  echo "⬇️  Installing Quartz $QUARTZ_REF into .quartz/ ..."
  git clone -q --depth 1 --branch "$QUARTZ_REF" https://github.com/jackyzha0/quartz.git "$QZ"
  (cd "$QZ" && npm ci --no-audit --no-fund)
fi
if [ ! -f "$QZ/quartz.config.yaml" ]; then
  (cd "$QZ" && npx quartz create -t default -X new -l absolute -b "$QUARTZ_BASE_URL")
fi

# Site title, Korean locale, base URL, absolute [[dir/page]] links.
QUARTZ_BASE_URL="$QUARTZ_BASE_URL" "$PY" "$ROOT/scripts/quartz_config.py" "$QZ/quartz.config.yaml" "$CORPUS"

if [ ! -f "$QZ/.plugins-installed" ]; then
  # Plugins pinned in quartz.lock.json, then any enabled in the config but not locked.
  (cd "$QZ" && npx quartz plugin install && npx quartz plugin resolve) || exit 1
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
