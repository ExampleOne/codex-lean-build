# Building the binary

On a normal network, `./build.sh` just works: it copies the source, applies the lean
optimisations, and runs `cargo build --release -p codex-cli --bin codex`. Cargo
downloads two large prebuilt native libraries on the way — `rusty_v8` (~32 MB) and
`libwebrtc` (~243 MB) — for the embedded JS engine and the realtime-voice stack that
`codex-cli` pulls in transitively (a formaliser uses neither).

## Behind a throttling VPN / proxy (the gotcha)

Some VPN/proxy gateways **504 or truncate large single transfers** while allowing
small requests. Symptoms:
- `v8` build fails with `Decompression error Err(Buf)`, or later a rustc panic in
  `rustc_codegen_ssa/.../archive.rs` (a **corrupt/truncated `librusty_v8.a`**).
- `webrtc-sys` fails with `failed to download webrtc: 504 Gateway Timeout`.

These are **environment** failures, not the Lean changes. The fix is to fetch both
prebuilts in **parallel HTTP range chunks** (which slip under the gateway) and hand
them to the build via env vars so it never makes the failing transfer:

- `RUSTY_V8_ARCHIVE=<path to librusty_v8.a.gz>` — v8 copies/decompresses this instead
  of downloading. Asset: `https://github.com/denoland/rusty_v8/releases/download/v<ver>/librusty_v8_release_<target>.a.gz`.
- `LK_CUSTOM_WEBRTC=<dir containing include/ + lib/>` — webrtc-sys uses this local
  build. Asset: `https://github.com/livekit/rust-sdks/releases/download/<WEBRTC_TAG>/webrtc-<triple>.zip`.

`scripts/fetch-prebuilts-behind-proxy.sh` automates the v8 fetch + rebuild
(parallel-chunk download, gzip integrity check, `cargo clean -p v8`, build). Adapt the
URLs/paths for your target triple. The same parallel-chunk approach is what staged the
webrtc zip.

## Verified build (2026-06-08, aarch64-apple-darwin, behind VPN)

Produced a working 193 MB `codex` binary (`Finished release in 14m12s`). Confirmed it
embeds the lean system prompt (stock coding-agent prompt absent), and the
`[superseded diagnostics for …]` compaction stub. The codegen ICEs seen mid-debug were
all the corrupt `librusty_v8.a` — fixed by the clean parallel re-fetch above.

> Note: a `[profile.release.package.v8] opt-level = 0` override was added during
> debugging to reduce memory/ICE risk; it is harmless (v8 is thin FFI; the real work
> is in the prebuilt C++ lib) but not required once the archive is intact.
