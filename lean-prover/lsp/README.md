# Lean LSP prototype + benchmark (answer to "can a Lean LSP do better?")

A thin Lean 4 LSP client (`lean_lsp_client.py`) that gives an agent **diagnostics +
goal state** without `lake build`, and a benchmark (`bench.py`) comparing its token
cost to the `lake-quiet` wrapper this build already ships.

## Files
| File | What |
|---|---|
| `lean_lsp_client.py` | Working JSON-RPC client to `lake serve`: `didOpen` → diagnostics, `$/lean/plainGoal` → tactic goal. Runs live against any Lean project. |
| `bench.py` | Tokenizes raw lake vs `lake-quiet` vs LSP across 3 scenarios. |
| `samples/` | Representative inputs in real Lean-LSP / lake formats. |

## Result (o200k_base)

```
Mechanism             raw     lake-quiet      LSP    quiet vs raw   LSP vs quiet
S1 error feedback     131          71          34         46%           52%
S2 lemma search       717         717          64          0%           91%
S3 recheck (clean)   5021          10           9        100%           10%
TOTAL                5869         798         107         86%           87%
```

## What this actually shows (the honest read)

The LSP does **not** meaningfully beat `lake-quiet` on build-error feedback:
- **S3 (recheck a clean file in a Mathlib project): a wash** — `lake-quiet` already
  strips the thousands of `[n/m] Building Mathlib.X` progress lines (5021 → 10 tok),
  so the LSP's "no build log" advantage is *already captured* by the wrapper.
- **S1 (one error): modest** — 71 → 34 tok; real but small in absolute terms.

The LSP's distinctive, **additive** win is:
- **S2 (lemma discovery): ~91%** — replacing `grep`-ing Mathlib (717 tok of matches
  across dozens of files, often repeated as the agent guesses names) with a
  structured `exact?`/`leansearch`-style result (64 tok of typed candidates). This
  is something `lake-quiet` cannot do at all.

So the earlier "structured diagnostics instead of build logs is a big win" claim was
**overstated** — `lake-quiet` already does most of that. The truthful conclusion:

> An LSP's token value is concentrated in **lemma search**, not diagnostics. Its
> other real benefit is **latency**: incremental, in-memory checking + precise
> goal queries avoid full rebuilds, which reduces the *number of turns* — and since
> every turn replays the growing transcript, fewer turns is where the big cumulative
> saving lives. That latency/turn-count win is not visible in a per-message token
> table; it needs an end-to-end proof-loop benchmark to quantify.

## Recommendation
Keep `lake-quiet` for build feedback. Add **one** LSP-backed tool surface focused on
lemma discovery + on-demand goal queries (not a full LSP suite — that re-adds schema
tokens). Net: small per-turn token change, but fewer turns and much cheaper lemma
lookup.

## Wired in: lean-lsp-mcp (done)

Rather than ship the hand-rolled `lean_lsp_client.py`, the build now wires in the
mature **[lean-lsp-mcp](https://github.com/oOo0oOo/lean-lsp-mcp)** (MIT) — see
`patches/config.toml` (`[mcp_servers.lean-lsp]`) and the updated system prompt. We
expose only the 5 essential tools **directly** (`lean_goal`,
`lean_diagnostic_messages`, `lean_leansearch`, `lean_state_search`,
`lean_local_search`) via `LEAN_MCP_DISABLED_TOOLS`, and keep `tool_search` culled.

Token cost (measured by `measure_mcp_tools.py`, same method as the exact dump):

| | tok/turn |
|---|--:|
| 5 lean-lsp tool schemas | 747 |
| prompt growth (tool guidance) | +217 |
| **lean + lean-lsp (instr+tools)** | **2411** |
| stock Codex (instr+tools) | 6269 |
| **still under stock** | **62%** |

So adding the LSP capability keeps us far under stock *and* buys the 91% lemma-search
win. **Exposure note:** direct is correct for this small always-used set; if you ever
expose the full ~11-tool suite or add more MCP servers, re-enable `tool_search` so
Codex **defers** their schemas (`mcp_tool_exposure.rs`: `should_defer` requires
`search_tool_enabled`). Exact-to-the-byte numbers need a live dump with `uvx
lean-lsp-mcp` running (needs a Lean toolchain); this is the faithful schema-level cost.

## Run it live
The token install was blocked here, so the LSP numbers above are from reconstructed
(real-format) samples, not a live capture. To verify on a real machine:

```bash
# 1. install a Lean toolchain (elan) and build a project, e.g. a plain-Lean fixture
# 2. live diagnostics for one file:
python lean_lsp_client.py /path/to/project Example.lean 14 3
# 3. live benchmark:
/tmp/tkenv/bin/python bench.py --live /path/to/project Example.lean
```
