#!/usr/bin/env bash
# Build the wiki site with Quartz and publish it to the gh-pages branch of the
# origin repository, then make sure GitHub Pages serves that branch.
#
#   scripts/deploy_pages.sh [corpus]
#
# Only the static HTML is pushed (orphan gh-pages branch); the wiki Markdown
# itself is not committed to main.
set -euo pipefail

CORPUS=${1:-${WIKI_CORPUS:-assembly_spc}}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
slug=$(git -C "$ROOT" remote get-url origin | sed -E 's#(git@|https://)github.com[:/]##; s#\.git$##')

"$ROOT/scripts/quartz.sh" build "$CORPUS"
PUBLIC="$ROOT/.quartz/public"
touch "$PUBLIC/.nojekyll"

WT=$(mktemp -d)
trap 'git -C "$ROOT" worktree remove --force "$WT" >/dev/null 2>&1 || true' EXIT
if git -C "$ROOT" fetch -q origin gh-pages 2>/dev/null; then
  git -C "$ROOT" worktree add -q -B gh-pages "$WT" FETCH_HEAD
else
  git -C "$ROOT" branch -D gh-pages >/dev/null 2>&1 || true   # stale local branch from a failed push
  git -C "$ROOT" worktree add -q --detach "$WT"
  git -C "$WT" checkout -q --orphan gh-pages
  git -C "$WT" rm -rq . >/dev/null 2>&1 || true
fi
rsync -a --delete --exclude '.git' "$PUBLIC/" "$WT/"
git -C "$WT" add -A
if git -C "$WT" diff --cached --quiet; then
  echo "ℹ️  Site unchanged; nothing to deploy"
else
  git -C "$WT" commit -q -m "Deploy LLM-Wiki site ($CORPUS, $(date +%F))"
  # The site is tens of MB; the default HTTP post buffer makes GitHub answer 400.
  git -C "$WT" -c http.postBuffer=524288000 push -q origin gh-pages
  echo "🚀 Pushed gh-pages"
fi

if ! gh api "repos/$slug/pages" >/dev/null 2>&1; then
  echo '{"source":{"branch":"gh-pages","path":"/"}}' | gh api -X POST "repos/$slug/pages" --input - >/dev/null
  echo "📄 GitHub Pages enabled (source: gh-pages)"
fi
echo "🌐 https://${slug%%/*}.github.io/${slug##*/}/"
