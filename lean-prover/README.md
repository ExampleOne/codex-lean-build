# lean-prover

A single, token-optimised Codex build specialised for **autonomous Lean 4 / Mathlib
formalisation in a sandbox**. Unlike the comparative `variants/` series (a
cyber-safety ablation study), this is **not** a set of A/B variants — it is one
shipped, stripped-down build plus a documented versioning history of the
token-efficiency optimisations that produced it.

Goal: maximise token efficiency for a lean formaliser by removing everything a
theorem-proving agent doesn't use — general coding-agent prompt, planning/image/
multi-agent/MCP/web tools, and the per-turn approval narrative — and by compressing
the compiler output that otherwise dominates a proof loop.

## Headline result
**~79% reduction in fixed per-turn input overhead** (~7084 → ~1477 tokens),
**measured exactly** from the real serialized Responses-API request — not estimated.
Over a 50-turn proof-repair run that's ~280k input tokens saved on fixed overhead
alone. Full accounting and methodology: [`VERSIONS.md`](VERSIONS.md).

Exact numbers are reproducible from the committed wire dump:
```
python3 -m venv /tmp/tkenv && /tmp/tkenv/bin/pip install tiktoken
/tmp/tkenv/bin/python measurements/measure_exact.py     # exact, from the wire dump
# regenerate the dump itself:
cd codex-rs && cargo test -p codex-core --test all \
  suite::prompt_debug_tests::dump_real_request -- --nocapture
```

## Layout
| Path | What |
|---|---|
| `EFFICIENCY.md` | **Findings + measured numbers, and the two modes (start here)** |
| `lean-prover.toml` | **Single config** — prompt, tool culls, runtime knobs, lean-lsp tools |
| `VERSIONS.md` | Versioning history v0→v5 + exact token accounting |
| `prompt/lean_formaliser_prompt.md` · `…_no_lsp.md` | LSP-aware / shell+grep system prompts |
| `scripts/apply_lean_build.py` | Anchored patcher (reads `lean-prover.toml`): prompt swap + enabled culls |
| `scripts/gen_config.py` | Generates `patches/config.toml` + `config.no-lsp.toml` |
| `scripts/mcp_tools_list.py` | Audit the real lean-lsp tool surface + token cost |
| `measurements/measure_exact.py` | **Exact** token accounting from the real wire dump |
| `scripts/lake-quiet` | Compiler-output filter (point the shell tool at it) |
| `lsp/` | Lean LSP client + benchmark vs `lake-quiet` |
| `examples/` | `demo/` (no-Mathlib smoke test) · `sum-integral-swap/` (Mathlib runbook) |
| `BUILDING.md` | Build notes incl. the VPN/proxy prebuilt-fetch workaround |
| `build.sh` / `run.sh` | Build the optimised binary / run it with isolated state |

## Build & run
```
./build.sh                                   # copies ../codex-rs -> codex-lean, patches, cargo build
./run.sh exec "prove the lemmas in MyProject/Foo.lean"
./run.sh --no-lsp exec "..."                 # efficiency mode at runtime — no rebuild
```
`build.sh` keeps the main `../codex-rs` checkout pristine (it copies source into
`codex-lean/`). Compile-time optimisations are applied by `apply_lean_build.py`; runtime
ones live in `patches/config.toml` (installed into the isolated `CODEX_HOME` by `run.sh`).
**`--no-lsp`** swaps to the no-MCP config + the shell+grep prompt (via
`model_instructions_file`) at runtime — see [`EFFICIENCY.md`](EFFICIENCY.md) for the modes.

> Status: **validated** — `./build.sh` produces a 193 MB `codex` release binary that
> runs and is verified to embed the Lean prompt + tool culls + history compaction;
> the compaction is unit-tested and the token numbers come from the real wire dump.
> The one remaining gap is a live end-to-end run against a real Lean project (needs a
> Lean toolchain on the host). Build notes: [`BUILDING.md`](BUILDING.md).
