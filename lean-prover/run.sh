#!/usr/bin/env bash
#
# Run the optimised lean-formaliser build with its own isolated state + config.
#
# Usage:
#   ./run.sh                       # capability mode (lean-lsp + LSP-aware prompt)
#   ./run.sh exec "prove the lemmas in MyProject/Foo.lean"
#   ./run.sh --no-lsp exec "..."   # efficiency mode at RUNTIME (no rebuild):
#                                  # drops the lean-lsp MCP + swaps to the shell+grep
#                                  # prompt via model_instructions_file. ~76% under stock.
#   LEAN_NO_LSP=1 ./run.sh ...     # same, via env var
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="$HERE/codex-lean/codex-rs/target/release/codex"

# Consume our own --no-lsp flag so it isn't forwarded to codex.
NO_LSP="${LEAN_NO_LSP:-0}"
args=()
for a in "$@"; do
  case "$a" in
    --no-lsp) NO_LSP=1 ;;
    *) args+=("$a") ;;
  esac
done
set -- "${args[@]+"${args[@]}"}"

[[ -x "$BIN" ]] || { echo "Binary missing; run ./build.sh first." >&2; exit 1; }

# Isolated CODEX_HOME seeded with the lean config; carry over auth if present.
export CODEX_HOME="${CODEX_HOME:-$HERE/.codex-home}"
mkdir -p "$CODEX_HOME"
if [[ "$NO_LSP" == "1" ]]; then
  # Efficiency mode: no MCP, override the baked prompt with the shell+grep one.
  cp "$HERE/patches/config.no-lsp.toml" "$CODEX_HOME/config.toml"
  printf '\nmodel_instructions_file = "%s"\n' \
    "$HERE/prompt/lean_formaliser_prompt_no_lsp.md" >> "$CODEX_HOME/config.toml"
  echo ">> no-lsp mode: lean-lsp disabled, shell+grep prompt (runtime override)" >&2
else
  cp "$HERE/patches/config.toml" "$CODEX_HOME/config.toml"
fi
for f in auth.json .credentials.json; do
  [[ -f "$HOME/.codex/$f" && ! -f "$CODEX_HOME/$f" ]] && cp "$HOME/.codex/$f" "$CODEX_HOME/$f" || true
done

# Proof-tuned history compaction (history.rs) is env-gated; enable it from the manifest.
if python3 -c "import tomllib,sys;sys.exit(0 if tomllib.load(open('$HERE/lean-prover.toml','rb')).get('runtime',{}).get('compact_superseded_diagnostics') else 1)" 2>/dev/null; then
  export CODEX_COMPACT_SUPERSEDED_DIAGNOSTICS=1
fi

exec "$BIN" "$@"
