# codex-lean

A **token-optimised build of [OpenAI Codex](https://github.com/openai/codex)
specialised for autonomous Lean 4 / Mathlib formalisation.** It strips the general
coding agent down to what a theorem prover actually needs, so a long proof-repair
loop costs a fraction of the tokens.

> **Unofficial** derivative of OpenAI Codex (Apache-2.0). **Not** affiliated with or
> endorsed by OpenAI. "Codex" is used only to describe origin. See
> [`LICENSE`](LICENSE), [`NOTICE`](NOTICE), [`MODIFICATIONS.md`](MODIFICATIONS.md).

## Headline result

**~79% reduction in fixed per-turn input overhead** (~7084 → ~1477 tokens),
**measured exactly** from the real serialized Responses-API request — not estimated.
Over a 50-turn proof-repair run that's ~280k input tokens saved on fixed overhead
alone, before the output-side and history wins below.

Reproduce from the committed wire dump:
```bash
python3 -m venv /tmp/tkenv && /tmp/tkenv/bin/pip install tiktoken
/tmp/tkenv/bin/python lean-prover/measurements/measure_exact.py
```

## How it works

| Lever | What it does | Effect |
|---|---|---|
| **Lean system prompt** | Replaces the ~4371-tok general coding-agent prompt with a 391-tok formaliser prompt | −3980 tok/turn |
| **Tool cull** | Drops `update_plan`, `view_image`, `tool_search`, `request_user_input`, `web_search` | 1699 → 857 tok |
| **Sandbox-only** | `approval_policy=never`, no per-turn approval narrative | −785 tok/turn |
| **`lake-quiet`** | Strips build-progress noise from compiler output | ~63% per build |
| **lean-lsp-mcp** | Structured goals + lemma search instead of grepping Mathlib | 91% cheaper lemma lookup |
| **History compaction** | Stubs superseded diagnostics each turn (`history.rs`) | ~51–59% of cumulative diagnostics |
| **Prompt caching** | Fixed prompt+tools prefix is cache-stable | ~10× cheaper input on the prefix |

**Findings + measured numbers: [`lean-prover/EFFICIENCY.md`](lean-prover/EFFICIENCY.md)**
(start here). Version-by-version history: [`lean-prover/VERSIONS.md`](lean-prover/VERSIONS.md).
LSP analysis and benchmark: [`lean-prover/lsp/`](lean-prover/lsp/README.md).

### Two modes
A single switch trades capability for raw efficiency — set `[lean_lsp].enabled` at
build time, or flip it **at runtime** with `--no-lsp` (no rebuild):

| Mode | how | instr+tools/turn | vs stock |
|---|---|--:|--:|
| **Capability** (default) | `./run.sh …` | ~4167 | ~34% under |
| **Efficiency** | `./run.sh --no-lsp …` | ~1493 | **~76% under** |

## Build & run

```bash
cd lean-prover
./build.sh                                   # patch + cargo build the optimised binary
./run.sh exec "prove the lemmas in MyProject/Foo.lean"
./run.sh --no-lsp exec "..."                 # efficiency mode at runtime (no rebuild)
```
Everything is driven by one config file, **[`lean-prover/lean-prover.toml`](lean-prover/lean-prover.toml)**
(prompt, tool culls, runtime knobs, lean-lsp tools). Build notes — including the
parallel-fetch workaround for V8/WebRTC prebuilts behind a throttling VPN/proxy — are
in **[`lean-prover/BUILDING.md`](lean-prover/BUILDING.md)**.

## Status

- ✅ Builds: a 193 MB `codex` release binary that runs and is verified to embed the
  Lean prompt + tool culls + history compaction.
- ✅ Token numbers measured exactly from the real request; compaction unit-tested.
- ⏳ A live end-to-end run against a real Lean project requires a Lean toolchain
  (`elan` + Mathlib) on the host.

## Layout

| Path | What |
|---|---|
| `lean-prover/` | The optimisation layer, config, docs, measurements, LSP, build scripts |
| `codex-rs/` | The vendored Codex source it builds (with an additive measurement helper) |
| `MODIFICATIONS.md` | Exactly what changed vs upstream Codex (Apache-2.0 §4b) |

## License

Apache License 2.0 — see [`LICENSE`](LICENSE). This is a derivative work of OpenAI
Codex; upstream attribution is in [`NOTICE`](NOTICE) and the list of changes is in
[`MODIFICATIONS.md`](MODIFICATIONS.md).
