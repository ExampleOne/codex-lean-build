# lean-prover — versioning history & token-efficiency estimate

A token-optimised Codex build for a single purpose: **autonomous Lean 4 / Mathlib
formalisation in a sandbox**. Each version below is one optimisation step; the
shipped build (`v5`) is the cumulative result. All numbers are **input tokens paid
on every API turn** unless noted, measured with the `o200k_base` tokenizer
(GPT-5.x family) against the real source files. Reproduce with:

```
/tmp/tkenv/bin/python scripts/token_estimate.py
```

Target model: **gpt-5.2-codex** (most powerful codex model in this tree). Its system
prompt is assembled as `DEFAULT_PERSONALITY_HEADER + personality + BASE_INSTRUCTIONS`,
where `BASE_INSTRUCTIONS` == `codex-rs/models-manager/prompt.md` (byte-identical to
`protocol/.../base_instructions/default.md`).

> **Numbers below are EXACT** — measured from the real serialized Responses-API
> request, not estimated. The dump is produced by `build_request_debug` +
> `dump_real_request` (committed in `codex-rs/core/src/prompt_debug.rs` and
> `core/tests/suite/prompt_debug_tests.rs`) and tokenized by
> `measurements/measure_exact.py`. The earlier `scripts/token_estimate.py`
> over-counted the shell tool ~4× and missed three default-on tools; this dump
> supersedes it.

## Baseline (v0) — stock Codex per-turn fixed overhead (EXACT)

| Component | Tokens | Source |
|---|--:|---|
| System prompt (199 header + 4371 BASE_INSTRUCTIONS) | **4570** | wire dump |
| Tool schemas — 8 tools (see below) | **1699** | wire dump |
| Per-turn approval + sandbox narrative | ~815 | file size (not yet dumped) |
| **Fixed overhead / turn** | **~7084** | |

Exact per-tool wire cost (the dump corrected my estimates): `exec_command` 400,
`request_user_input` 345, `apply_patch` 262, `update_plan` 199, `write_stdin` 195,
`tool_search` 193, `view_image` 91, `web_search` 14. (Note: my earlier estimate put
`shell` at ~2409 — the real exec stack is 595. And `request_user_input`/`tool_search`
are ON by default, which static analysis missed.)

## Optimisation steps

### v1 — Lean formaliser system prompt  ·  −3980 tok/turn
Replace the 4371-tok general coding-agent prompt (AGENTS.md spec, preamble etiquette,
personality, frontend/git/PR guidance, sandbox-escalation narrative) with a
391-tok purpose-built formaliser prompt: edit→`lake build`→read errors→repeat,
zero-`sorry` exit condition, output discipline.
- Files: `prompt/lean_formaliser_prompt.md` → `models-manager/prompt.md` + `default.md`
- **BASE_INSTRUCTIONS 4371 → 391** (system prompt incl. header: 4570 → 590). Single biggest lever.

### v2 — Cull the tool set to {exec_command, write_stdin, apply_patch}  ·  −842 tok/turn (EXACT)
A formaliser needs an exec tool and an edit tool. The wire dump showed the default
set is 8 tools (1699 tok); we keep 3 (857 tok) and cull 5 (842 tok):
`update_plan` 199, `request_user_input` 345, `view_image` 91, `tool_search` 193,
`web_search` 14.
- `update_plan`, `view_image`, `tool_search` culled at compile time in
  `core/src/tools/spec_plan.rs` (handlers bound to `_` / forced early-return, so
  imports stay used and the build stays warning-clean).
- `request_user_input` + `web_search` disabled via `patches/config.toml`.
- Keeps the conditional heavyweights permanently off too: `multi_agents` (~5167),
  `mcp_resource`, `agent_jobs`.
- **1699 → 857 (exact).** (My earlier estimate said −271 because it over-counted
  `shell` and missed `request_user_input`/`tool_search` being default-on.)

### v3 — Sandbox-only, no per-turn permission narrative  ·  −785 tok/turn
`approval_policy = "never"` + `sandbox_mode = "workspace-write"` (config) drops the
758-tok on-request approval narrative and the workspace-write blurb to a single
hardcoded line. The lean prompt already states "no approval step." Also pins the
model and disables the hosted `web_search` tool and MCP (no servers configured).
- File: `patches/config.toml`
- **815 → 30.**

### v4 — Output-side: `lake-quiet` compiler-output filter  ·  ~63% on tool output (not fixed)
Not part of fixed overhead, but in a proof loop the *tool output* dominates context
because every prior turn's `lake build` log persists. `lake-quiet` strips progress
counters, `Building/Compiling X`, downloads, ANSI, and duplicate lines while
preserving every diagnostic and its goal state (`unsolved goals`, `⊢ …`, hypotheses).
- File: `scripts/lake-quiet` (point the shell tool at it instead of `lake`)
- Measured **63% reduction** on a representative error log; higher on real Mathlib
  builds that print thousands of progress lines.

## Cumulative result (shipped build = v1–v4) — EXACT

| | Tokens / turn |
|---|--:|
| instr + tools, baseline | 6269 |
| instr + tools, lean | 1447 |
| **instr + tools saving** | **4822 (77%)** |
| + permission narrative (est.) baseline / lean | ~7084 / ~1477 |
| **full fixed-overhead saving / turn** | **~5607 (~79%)** |

The exact dump revised the headline **up** from my earlier soft "58%": the system
prompt dominates (it's cut 87%) and the real tool payload is smaller than estimated,
so the prompt cut carries even more weight. Reproduce: `measurements/measure_exact.py`.

Plus a ~63% cut to the *fastest-growing* part of context (compiler output), which
compounds: it shrinks not just this turn's output but everything carried forward.

### What ~79% fixed + output compression means over a session

| Turns in a proof-repair run | Fixed-overhead tokens saved (~5607/turn) |
|--:|--:|
| 20 | ~112,000 |
| 50 | ~280,000 |
| 100 | ~560,000 |

On a realistic long Mathlib formalisation the output-side win (compiler output) can
exceed the fixed-overhead win; see the LSP analysis below for where the remaining
output/iteration savings actually live.

## Addendum — does a Lean LSP do better? (see `lsp/`)

Benchmarked a thin Lean LSP client against the `lake-quiet` wrapper (`lsp/bench.py`):

| Mechanism | raw | lake-quiet | LSP | LSP vs quiet |
|---|--:|--:|--:|--:|
| S1 error feedback | 131 | 71 | 34 | 52% |
| S2 lemma search | 717 | 717 | 64 | **91%** |
| S3 recheck (clean) | 5021 | 10 | 9 | 10% |

Honest finding: `lake-quiet` **already** removes the build-progress noise (S3), so the
LSP barely beats it on diagnostics. The LSP's distinctive, additive win is **lemma
discovery** (S2: structured search vs grepping Mathlib) plus **incremental checking
that cuts the number of turns** (latency, not per-message tokens).

### v5 — Wire in lean-lsp-mcp  ·  MEASURED LIVE (corrected)
The build wires the mature [lean-lsp-mcp](https://github.com/oOo0oOo/lean-lsp-mcp)
(MIT) via `patches/config.toml`, exposing only `lean_goal`,
`lean_diagnostic_messages`, `lean_leansearch`, `lean_local_search` **directly**
(`LEAN_MCP_DISABLED_TOOLS`), with `tool_search` kept culled.

> **Correction (live measurement, 2026-06-08):** querying the *installed* server's
> `tools/list` (`scripts/mcp_tools_list.py`) showed it actually exposes **22 tools**
> (names drift across versions; the deny-list is a DENY list), and the real schemas
> are far richer than my hand-built estimate — **the 5-tool set is 2870 tok, not 747.**
> `goal` (807) + `diagnostic_messages` (869) alone are 1676 and are unavoidable. I
> trimmed to **4 tools (drop `lean_state_search`, overlaps leansearch) = 2503 tok.**

| | tok/turn |
|---|--:|
| lean instr (with lsp guidance) | 807 |
| codex tools kept (exec/write_stdin/apply_patch) | 857 |
| 4 lean-lsp tool schemas (real) | 2503 |
| **lean + lean-lsp** | **4167** |
| vs stock Codex 6269 | **~34% under** |

The lean-lsp tools eat much of the prompt/tool savings, so the headline is **~34%
under stock**, not the 62% an earlier estimate implied. Prompt caching keeps this in
the cheap cached prefix; the larger recurring wins are on the uncached side
(`lake-quiet`, LSP diagnostics, compaction). **For absolute minimum prefix**, set
`cull.tool_search = false` (manifest) to DEFER the verbose schemas — best with these
~575-tok-each tools, but it needs a rebuild. Measured: `scripts/mcp_tools_list.py`.

### Build modes — one switch: `[lean_lsp].enabled`
A single manifest flag picks the capability-vs-efficiency tradeoff. It selects the
system prompt (`apply_lean_build.py`) *and* whether the MCP server is configured
(`gen_config.py`), so the two never disagree:

| mode | `[lean_lsp].enabled` | prompt | tools | instr+tools | vs stock |
|---|---|---|---|--:|--:|
| **Capability** | `true` | LSP-aware (582 tok) | exec/apply_patch + 4 lean-lsp | ~4167 | ~34% under |
| **Efficiency** | `false` | shell+grep (437 tok) | exec/apply_patch only | ~1493 | **~76% under** |

Efficiency mode drops the lemma-search tools (the agent uses `lake-quiet` + `grep`
over `.lake/packages/mathlib/`); capability mode buys structured goals + the 91%
lemma-search win for ~2.7k tok/turn (cached in the prefix). Default is `true`.

## Build configuration

All the above is driven by **`lean-prover.toml`** (single source of truth): the system
prompt file, which compile-time culls to apply (`[cull]`), runtime knobs (`[runtime]`),
and the lean-lsp tool set (`[lean_lsp]`). `scripts/apply_lean_build.py` reads it for the
compile-time patches; `scripts/gen_config.py` generates `patches/config.toml` from it.
`build.sh` runs both. Change behaviour without touching scripts or config by hand.

## Verified / prototyped (the recommended next steps)

### Prompt caching — VERIFIED engaged
`client.rs::prompt_cache_key()` returns the `thread_id`, stable across all turns in a
session, and the cached prefix is `instructions` + `tools` (both static in this build;
`environment_context`/date lives in the *input*, after the prefix). So from turn 2 the
fixed system-prompt+tools prefix bills as cached (~10× cheaper input). **Opportunity:**
a *constant* cache key would share that prefix across *all* proof sessions (a fleet),
not just within one — currently only wired for guardian review sessions
(`with_prompt_cache_key_override`); exposing it generally is a small hook. Reserved as
`[cache].prompt_cache_key` in `lean-prover.toml`.

### Proof-tuned history compaction — LANDED (Rust, tested)
Implemented in `context_manager/history.rs::for_prompt`: each turn, superseded
diagnostic/build tool outputs are replaced with a one-line stub, keeping only the
latest output per `(tool, target)` — `lean_diagnostic_messages` per file,
`lean_build`/`lake build` globally (`lean_goal` left untouched: it's positional).
Gated by `CODEX_COMPACT_SUPERSEDED_DIAGNOSTICS` (off by default; `run.sh` exports it
from `lean-prover.toml [runtime].compact_superseded_diagnostics`). Unit-tested
(`compacts_superseded_diagnostics_keeping_latest_per_file`).

What it buys (`scripts/compaction_prototype.py`): over a 30-turn repair loop, **~51–59%**
fewer cumulative diagnostic input tokens (final-turn context ~1530→~600). Also removes
already-fixed errors that could mislead the model. **Caching interaction:** rewriting an
older output is a one-time cache miss for that region; the stub is then stable and
re-caches, so the net is positive. Complements `lake-quiet` (per-output filter).

## Further work (additional headroom, not yet applied)
- **Strip the personality scaffold** in `models-manager/src/model_info.rs` (ship
  `BASE_INSTRUCTIONS` raw instead of `DEFAULT_PERSONALITY_HEADER + … + BASE_INSTRUCTIONS`).
  ~35 tok/turn — left out of the automated patcher to avoid orphaning the two
  personality consts; trivial to apply by hand alongside their removal.
- **Slim the `shell` tool description** for a single fixed environment — the largest
  remaining model-visible cost. Realistic target ~600–900 tok (from the ~2.4k spec).
- **Replace freeform `apply_patch`** (752-tok grammar in-prompt) with a minimal
  line-range edit tool (~300 tok) — Lean edits are small and localised.
- **Trim the environment-context block** (`environment_context.rs`) to cwd + Lean
  toolchain version; drop network/permission XML.
- **Expose `prompt_cache_key`** generally (constant key) for cross-session cache reuse.
- **Compile the full release binary** (`./build.sh`) to validate all edits together.
