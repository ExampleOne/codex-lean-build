#!/usr/bin/env bash
# Fetch a NON-corrupt rusty_v8 prebuilt (parallel chunks, bypassing the VPN
# throttle that truncated the original), then rebuild pointing v8 + webrtc at the
# local archives. This is the real fix: the archive.rs panic = a corrupt librusty_v8.a.
set -uo pipefail
URL="https://github.com/denoland/rusty_v8/releases/download/v147.4.0/librusty_v8_release_aarch64-apple-darwin.a.gz"
STAGE=/Users/quintentupker/coding/custom-codex/lean-prover/.webrtc-prebuilt
GZ="$STAGE/librusty_v8.a.gz"; PARTS="$STAGE/v8parts"
RS=/Users/quintentupker/coding/custom-codex/lean-prover/codex-lean/codex-rs
WEBRTC="$STAGE/extract/mac-arm64-release"
N=8
rm -rf "$PARTS" "$GZ"; mkdir -p "$PARTS"
resolve(){ curl -s -o /dev/null -w '%{redirect_url}' "$URL"; }
TOTAL=$(curl -sIL --max-time 60 "$URL" | awk 'tolower($1)=="content-length:"{v=$2}END{gsub(/\r/,"",v);print v}')
echo ">> v8 archive TOTAL=$TOTAL"
[ -n "$TOTAL" ] && [ "$TOTAL" -gt 1000000 ] || { echo "bad TOTAL"; exit 1; }
seg=$(( (TOTAL + N - 1)/N ))
worker(){ local i=$1 s=$2 e=$3 out="$PARTS/p$1" want=$(($3-$2+1))
  for a in $(seq 1 40); do local h; h=$(stat -f%z "$out" 2>/dev/null||echo 0); [ "$h" -ge "$want" ] && return 0
    local u; u=$(resolve); [ -n "$u" ]||u="$URL"; curl -s --max-time 300 --range "$((s+h))-$e" "$u" >> "$out"||true; sleep 1; done
  local h; h=$(stat -f%z "$out" 2>/dev/null||echo 0); [ "$h" -ge "$want" ]; }
pids=(); for i in $(seq 0 $((N-1))); do s=$((i*seg)); [ "$s" -ge "$TOTAL" ]&&break; e=$((s+seg-1)); [ "$e" -ge "$TOTAL" ]&&e=$((TOTAL-1)); : > "$PARTS/p$i"; worker $i $s $e & pids+=($!); done
f=0; for p in "${pids[@]}"; do wait "$p"||f=1; done; [ "$f" = 0 ]||{ echo "download failed"; exit 1; }
: > "$GZ"; for i in $(seq 0 $((N-1))); do [ -f "$PARTS/p$i" ]&&cat "$PARTS/p$i" >> "$GZ"; done
FINAL=$(stat -f%z "$GZ"); echo ">> got $FINAL / $TOTAL"; [ "$FINAL" = "$TOTAL" ]||{ echo "size mismatch"; exit 1; }
gzip -t "$GZ" || { echo ">> GZIP INTEGRITY FAIL (still corrupt)"; exit 1; }
echo ">> v8 archive integrity OK"
rm -rf "$PARTS"

cd "$RS"
export RUSTY_V8_ARCHIVE="$GZ" LK_CUSTOM_WEBRTC="$WEBRTC"
echo ">> forcing v8 to regenerate from the good archive"
cargo clean -p v8 --release 2>/dev/null || true
echo ">> building codex"
cargo build --release -p codex-cli --bin codex; echo "BUILD_EXIT=$?"
