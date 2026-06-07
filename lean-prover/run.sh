#!/usr/bin/env bash
#
# Run the optimised lean-formaliser build with its own isolated state + config.
#
# Usage:
#   ./run.sh                       # interactive
#   ./run.sh exec "prove the lemmas in MyProject/Foo.lean"
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/codex-lean/codex-rs/target/release/codex"

[[ -x "$BIN" ]] || { echo "Binary missing; run ./build.sh first." >&2; exit 1; }

# Isolated CODEX_HOME seeded with the lean config; carry over auth if present.
export CODEX_HOME="${CODEX_HOME:-$HERE/.codex-home}"
mkdir -p "$CODEX_HOME"
cp "$HERE/patches/config.toml" "$CODEX_HOME/config.toml"
for f in auth.json .credentials.json; do
  [[ -f "$HOME/.codex/$f" && ! -f "$CODEX_HOME/$f" ]] && cp "$HOME/.codex/$f" "$CODEX_HOME/$f" || true
done

exec "$BIN" "$@"
