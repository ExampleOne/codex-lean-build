# Token efficiency — findings

What makes codex-lean cheaper than stock Codex for Lean work, with the **measured**
numbers (o200k_base) and the surprises that turned up when we ran it for real. The
version-by-version history is in [`VERSIONS.md`](VERSIONS.md); this is the summary.

## Two modes (one switch)

`[lean_lsp].enabled` in `lean-prover.toml` is the master capability-vs-efficiency
switch. It can also be flipped **at runtime** with `./run.sh --no-lsp` (no rebuild).

| Mode | how | prompt | tools | instr+tools/turn | vs stock (6269) |
|---|---|---|---|--:|--:|
| **Capability** (default) | `enabled=true` / `./run.sh` | LSP-aware (582 tok) | exec/apply_patch + 4 lean-lsp | **~4167** | ~34% under |
| **Efficiency** | `enabled=false` / `./run.sh --no-lsp` | shell+grep (437 tok) | exec/apply_patch only | **~1493** | **~76% under** |

Capability mode buys structured goal/diagnostic access and lemma search; efficiency
mode has the agent use `lake-quiet` + `grep` over Mathlib instead. Runtime `--no-lsp`
drops the MCP server and overrides the baked prompt via `model_instructions_file`
(Codex precedence: config base-instructions > history > baked model prompt).

## Where the savings come from (measured)

| Lever | Stock | Lean | Note |
|---|--:|--:|---|
| System prompt | 4570 | ~590 | purpose-built formaliser prompt replaces the general agent prompt |
| Built-in tools | 1699 (8 tools) | 857 (exec+apply_patch) | culled update_plan/view_image/tool_search/web_search/request_user_input |
| Per-turn approval narrative | ~815 | ~30 | sandbox-only, `approval_policy=never` |
| **Fixed overhead (no lean-lsp)** | **~7084** | **~1493** | **~79% under** — exact, from the real serialized request |

Plus the output-side and history levers, which attack the *fastest-growing* costs:

| Lever | Real measurement | Source |
|---|--:|---|
| `lake-quiet` (filter Lake noise) | **66%** off a real failing build | live `lake build` on `examples/demo/` |
| lean-lsp diagnostics vs raw build | **71%** off | live LSP on the same file |
| Lemma search vs `grep` Mathlib | **~91%** off | benchmark (`lsp/bench.py`) |
| History compaction (drop superseded diagnostics) | **51–59%** of cumulative diagnostics | `scripts/compaction_prototype.py` (Rust impl in `history.rs`) |
| Prompt caching | ~10× cheaper on the fixed prefix | engaged; key = thread_id, prefix = instr+tools |

## Findings that only surfaced by running it

- **The lean-lsp tools are expensive.** The installed server's real schemas cost
  **2870 tok for 5 tools** (`lean_goal` 807 + `lean_diagnostic_messages` 869 alone are
  1676), not the ~747 a hand-built estimate suggested — so capability mode is ~34%
  under stock, not the 62% an early estimate implied. We trimmed to 4 tools.
- **Tool names drift across versions.** `tools/list` showed the installed server
  exposes **22 tools**, and `LEAN_MCP_DISABLED_TOOLS` is a *deny* list — so a stale
  list silently leaked tools. Re-audit with `scripts/mcp_tools_list.py` after upgrades.
- **`lake-quiet` had a real bug.** On a real build it cut 0% because it didn't filter
  Lake's `trace:` / glyph-prefixed `✖ [2/3]` lines. Fixed → 66%. (Representative
  samples had hidden this.)
- **The build pulls heavy native deps.** `codex-cli` drags in V8 + WebRTC prebuilts a
  formaliser never uses; behind a throttling VPN these fail and must be parallel-chunk
  fetched (see [`BUILDING.md`](BUILDING.md)). The "compiler ICEs" we chased were really
  a VPN-truncated `librusty_v8.a`.

## Reproduce

```bash
python3 -m venv /tmp/tkenv && /tmp/tkenv/bin/pip install tiktoken
/tmp/tkenv/bin/python measurements/measure_exact.py      # fixed overhead, from the real request
python3 scripts/mcp_tools_list.py <lean-project>         # live tool surface + token cost
/tmp/tkenv/bin/python scripts/compaction_prototype.py    # history-compaction win
```
