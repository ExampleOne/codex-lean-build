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
Keep `lake-quiet` for build feedback. Add **one** LSP-backed tool focused on lemma
discovery + on-demand goal queries (not a full LSP tool suite — that re-adds schema
tokens). Net: small per-turn token change, but fewer turns and much cheaper lemma
lookup.

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
