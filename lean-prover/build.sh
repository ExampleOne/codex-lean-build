#!/usr/bin/env bash
#
# Build the single optimised lean-formaliser Codex binary.
#
# Strategy: copy the pristine ../codex-rs source into ./codex-lean (source only,
# no target/), apply the lean optimisations, then cargo-build. The copy keeps the
# main checkout pristine and makes this a self-contained shippable build.
#
# Usage:
#   ./build.sh              # copy (if needed), patch, build release binary
#   FORCE_COPY=1 ./build.sh # re-copy fresh source before patching
#   SKIP_BUILD=1 ./build.sh # copy + patch only (no cargo build)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../codex-rs"
DST="$HERE/codex-lean/codex-rs"

if [[ "${FORCE_COPY:-0}" == "1" || ! -d "$DST" ]]; then
  echo ">> Copying source -> codex-lean (excluding target/, .git)..." >&2
  mkdir -p "$DST"
  rsync -a --delete \
    --exclude 'target/' --exclude '.git/' --exclude 'node_modules/' \
    "$SRC/" "$DST/"
fi

echo ">> Applying lean optimisations..." >&2
python3 "$HERE/scripts/apply_lean_build.py" "$DST"

# Install the lake-quiet wrapper next to the build for convenience.
install -m 0755 "$HERE/scripts/lake-quiet" "$HERE/codex-lean/lake-quiet"

if [[ "${SKIP_BUILD:-0}" == "1" ]]; then
  echo ">> SKIP_BUILD set; patched source ready at $DST" >&2
  exit 0
fi

echo ">> Building release binary (first build is slow)..." >&2
( cd "$DST" && cargo build --release -p codex-cli --bin codex )
echo ">> Binary: $DST/target/release/codex" >&2
