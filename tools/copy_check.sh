#!/usr/bin/env bash
# BUILD_SPEC ground rules 1 and 6, and section 11: the copy gate.
#
#   - the company is never named, anywhere
#   - no em dashes: colons or parentheses instead
#   - no forbidden words
#
# Vendored third-party code is excluded. It is not our copy, we did not write it, and
# Plotly's minified bundle contains an em dash in a CSS string: failing the build on that
# would train everyone to ignore this check, which is worse than not having it.
#
# Run from the repo root:  bash tools/copy_check.sh
set -uo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# This script is excluded from its own scan for the reason BUILD_SPEC.md is excluded from the
# word list: it has to spell out the name, the words and the dash it forbids, so it always
# matched itself and the gate could never pass.
EXCLUDE=(':!web/js/vendor' ':!web/css/molstar.css' ':!papers' ':!docs/screenshots' ':!tools/copy_check.sh')
FAIL=0

say() { printf '%s\n' "$1"; }

# 1. The company name, in any casing. BUILD_SPEC 1.1.
if git grep -In -i -e 'incyte' -- . "${EXCLUDE[@]}" > /tmp/gc_copy_company 2>/dev/null; then
  say "FAIL  the company is named:"; sed 's/^/        /' /tmp/gc_copy_company | head -10; FAIL=1
else
  say "ok    the company is never named"
fi

# 2. Em dashes. BUILD_SPEC 1.6.
if git grep -In $'—' -- . "${EXCLUDE[@]}" > /tmp/gc_copy_dash 2>/dev/null; then
  say "FAIL  em dash found:"; sed 's/^/        /' /tmp/gc_copy_dash | head -10; FAIL=1
else
  say "ok    no em dashes"
fi

# 3. Forbidden words. BUILD_SPEC 1.6. 'leverage' only as a verb, so it is checked by hand.
# BUILD_SPEC.md is excluded here and only here: the rule that forbids these words has to
# name them, and failing the build on the specification quoting its own vocabulary would
# make this check something everyone learns to skip.
WORDS=(groundbreaking revolutionary paradigm-shifting game-changing cutting-edge delve)
found_word=0
for w in "${WORDS[@]}"; do
  if git grep -Iniw -e "$w" -- . "${EXCLUDE[@]}" ':!BUILD_SPEC.md' > /tmp/gc_copy_word 2>/dev/null; then
    say "FAIL  forbidden word '$w':"; sed 's/^/        /' /tmp/gc_copy_word | head -5; FAIL=1; found_word=1
  fi
done
[ $found_word -eq 0 ] && say "ok    no forbidden words"

# 4. British English spellings that commonly slip in.
if git grep -Iniw -e 'color' -e 'behavior' -e 'organize' -e 'analyze' -- \
     '*.md' 'pipeline/raw/**/*.json' 'pipeline/raw/**/*.tsv' ':!BUILD_SPEC.md' > /tmp/gc_copy_us 2>/dev/null; then
  say "note  US spellings in prose (CSS properties and API fields are fine):"
  sed 's/^/        /' /tmp/gc_copy_us | head -5
fi

rm -f /tmp/gc_copy_company /tmp/gc_copy_dash /tmp/gc_copy_word /tmp/gc_copy_us
[ $FAIL -eq 0 ] && { say ""; say "copy check passed"; exit 0; }
say ""; say "copy check FAILED"; exit 1
