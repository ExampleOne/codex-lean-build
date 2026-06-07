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
| `VERSIONS.md` | Versioning history v0→v4 + exact token accounting (start here) |
| `prompt/lean_formaliser_prompt.md` | The 391-tok system prompt (replaces the 4371-tok default) |
| `scripts/apply_lean_build.py` | Anchored patcher: prompt swap + tool cull on a `codex-rs` checkout |
| `measurements/measure_exact.py` | **Exact** token accounting from the real wire dump |
| `measurements/baseline_*.{txt,json}` | Committed snapshot of the real serialized request |
| `scripts/token_estimate.py` | Older source-literal *estimate* (superseded by measure_exact) |
| `scripts/lake-quiet` | Compiler-output filter (point the shell tool at it) |
| `lsp/` | Thin Lean LSP client + benchmark vs `lake-quiet` (answer to "can an LSP do better?") |
| `patches/config.toml` | Runtime config: pin gpt-5.2-codex, sandbox-only, no web/MCP/user-input |
| `build.sh` / `run.sh` | Build the optimised binary / run it with isolated state |

## Build & run
```
./build.sh        # copies ../codex-rs -> codex-lean, applies optimisations, cargo build
./run.sh exec "prove the lemmas in MyProject/Foo.lean"
```
`build.sh` keeps the main `../codex-rs` checkout pristine (it copies source into
`codex-lean/`). The compile-time optimisations are applied by `apply_lean_build.py`;
the runtime ones live in `patches/config.toml` (installed into the isolated
`CODEX_HOME` by `run.sh`).

> Status: the prompt, config, wrapper, estimate, and patcher are complete and the
> patcher is anchored/idempotent. A full `cargo build` to validate compilation of
> the registry edits has **not** been run here — do that with `./build.sh` before
> shipping.
