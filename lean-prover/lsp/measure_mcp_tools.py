#!/usr/bin/env python3
"""Token cost of wiring lean-lsp-mcp into the lean build.

Builds the Responses-API JSON schema for the essential lean-lsp-mcp tools (verbatim
names/descriptions/params from the server source) and tokenizes them, the same way
measure_exact.py tokenized Codex's own tools. Then computes the NET per-turn budget:
  lean baseline (exact dump)  +  lean-lsp tools  =  lean+lsp build.

Exact-to-the-byte numbers require a live dump with the server running (needs a Lean
toolchain + uvx); this is a faithful schema-level estimate of that cost.

Run:  /tmp/tkenv/bin/python measure_mcp_tools.py
"""
import json
import tiktoken

ENC = tiktoken.get_encoding("o200k_base")
tok = lambda o: len(ENC.encode(json.dumps(o)))

# Codex namespaces MCP tools; emulate the prefix so the name cost is realistic.
NS = "lean-lsp__"

TOOLS = {
    "lean_goal": {
        "type": "function", "name": NS + "lean_goal",
        "description": ("Get proof goals at a position. MOST IMPORTANT tool - use often! "
                        "Omit column to see goals_before (line start) and goals_after (line end), "
                        "showing how the tactic transforms the state. \"no goals\" = proof complete."),
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string", "description": "Absolute or project-root-relative path to Lean file"},
            "line": {"type": "integer", "description": "Line number (1-indexed)"},
            "column": {"type": "integer", "description": "Column (1-indexed). Omit for before/after"},
            "format": {"type": "string", "enum": ["text", "structured"], "description": "Output format (default: text)"},
        }, "required": ["file_path", "line"], "additionalProperties": False},
    },
    "lean_diagnostic_messages": {
        "type": "function", "name": NS + "lean_diagnostic_messages",
        "description": "Get compiler diagnostics (errors, warnings, infos) for a Lean file.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string", "description": "Absolute or project-root-relative path to Lean file"},
            "start_line": {"type": "integer", "description": "Filter from line"},
            "end_line": {"type": "integer", "description": "Filter to line"},
            "severity": {"type": "integer", "description": "Filter by severity level"},
        }, "required": ["file_path"], "additionalProperties": False},
    },
    "lean_leansearch": {
        "type": "function", "name": NS + "lean_leansearch",
        "description": ("Search Mathlib via leansearch.net using natural language. Examples: "
                        "\"sum of two even numbers is even\", \"Cauchy-Schwarz inequality\", "
                        "\"{f : A -> B} (hf : Injective f) : exists g, LeftInverse g f\""),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Natural language or Lean term query"},
            "num_results": {"type": "integer", "description": "Max results (default: 5)"},
        }, "required": ["query"], "additionalProperties": False},
    },
    "lean_state_search": {
        "type": "function", "name": NS + "lean_state_search",
        "description": "Find lemmas to close the goal at a position. Searches premise-search.com.",
        "parameters": {"type": "object", "properties": {
            "file_path": {"type": "string", "description": "Absolute or project-root-relative path to Lean file"},
            "line": {"type": "integer", "description": "Line number (1-indexed)"},
            "column": {"type": "integer", "description": "Column number (1-indexed)"},
            "num_results": {"type": "integer", "description": "Max results (default: 5)"},
        }, "required": ["file_path", "line", "column"], "additionalProperties": False},
    },
    "lean_local_search": {
        "type": "function", "name": NS + "lean_local_search",
        "description": "Fast local search to verify declarations exist. Use BEFORE trying a lemma name.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Declaration name or prefix"},
            "limit": {"type": "integer", "description": "Max matches (default: 10)"},
        }, "required": ["query"], "additionalProperties": False},
    },
}

print("== lean-lsp-mcp essential tool schemas (o200k_base) ==")
total = 0
for name, spec in TOOLS.items():
    t = tok(spec)
    total += t
    print(f"  {t:>4}  {name}")
print(f"  ----")
print(f"  {total:>4}  TOTAL (5 essential tools, exposed DIRECT — tool_search stays culled)\n")

# Net budget vs the exact dump numbers (measurements/measure_exact.py).
LEAN_INSTR, LEAN_TOOLS = 590, 857          # exec_command+write_stdin+apply_patch
PROMPT_ADD = 217   # measured: lean prompt grew from 391 to 608 for the lean-lsp tool guidance
BASELINE_FIXED = 6269                       # stock instr+tools (exact)

lean = LEAN_INSTR + LEAN_TOOLS
lean_lsp = lean + total + PROMPT_ADD
print("== net per-turn fixed overhead (instr + tools) ==")
print(f"  stock Codex                 {BASELINE_FIXED}")
print(f"  lean (no lsp)               {lean}")
print(f"  lean + lean-lsp (5 tools)   {lean_lsp}   (still {100*(BASELINE_FIXED-lean_lsp)/BASELINE_FIXED:.0f}% under stock)")
print()
print(f"  Optional: if lean-lsp replaces lake-via-shell, drop exec_command+write_stdin (-595):")
print(f"  lean + lean-lsp - shell     {lean_lsp - 595}   ({100*(BASELINE_FIXED-(lean_lsp-595))/BASELINE_FIXED:.0f}% under stock)")
print()
print("Exposure choice: for this small, always-used 5-tool set, DIRECT is right — the")
print("schemas are always available with no discovery round-trip. If you later expose")
print("the FULL ~11-tool lean-lsp suite or add more MCP servers, re-enable tool_search")
print("so they DEFER (load on demand) instead of shipping every schema every turn.")
