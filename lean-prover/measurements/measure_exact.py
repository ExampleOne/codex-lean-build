#!/usr/bin/env python3
"""Exact per-turn token accounting from the REAL Responses-API wire dump.

Unlike scripts/token_estimate.py (which estimates tool cost from spec literals),
this reads the actual serialized request produced by codex-rs and tokenizes it, so
the instructions + tools numbers are ground truth, not estimates.

Regenerate the dump (writes /tmp/codex_dump_*):
    cd ../../codex-rs && cargo test -p codex-core --test all \
        suite::prompt_debug_tests::dump_real_request -- --nocapture
(The test + the `build_request_debug` helper it calls are committed in codex-rs:
 core/src/prompt_debug.rs and core/tests/suite/prompt_debug_tests.rs.)

Then:  /tmp/tkenv/bin/python measure_exact.py
Defaults to the committed snapshot in this folder if /tmp dump is absent.
"""
import json
import os

import tiktoken

ENC = tiktoken.get_encoding("o200k_base")
tok = lambda s: len(ENC.encode(s))
HERE = os.path.dirname(os.path.abspath(__file__))

instr_path = "/tmp/codex_dump_instructions.txt"
tools_path = "/tmp/codex_dump_tools.json"
if not os.path.exists(instr_path):
    instr_path = os.path.join(HERE, "baseline_instructions.txt")
    tools_path = os.path.join(HERE, "baseline_tools.json")

instr = open(instr_path).read()
tools = json.load(open(tools_path))

LEAN_PROMPT = os.path.join(HERE, "..", "prompt", "lean_formaliser_prompt.md")
lean_prompt = tok(open(LEAN_PROMPT).read())

# Tools the lean build keeps (everything else is culled at compile-time or via config).
KEEP = {"exec_command", "write_stdin", "apply_patch"}

by = {(t.get("name") or t.get("type")): tok(json.dumps(t)) for t in tools}
instr_exact = tok(instr)
base_instr_only = tok(open(os.path.join(HERE, "..", "..", "codex-rs",
                                       "models-manager", "prompt.md")).read())
header = instr_exact - base_instr_only  # personality header + placeholder

base_tools = sum(by.values())
lean_tools = sum(v for k, v in by.items() if k in KEEP)
culled = {k: v for k, v in by.items() if k not in KEEP}

print(f"source: {os.path.relpath(instr_path)}  (o200k_base)\n")
print("== instructions ==")
print(f"  baseline   {instr_exact:>5}  ({header} header + {base_instr_only} BASE_INSTRUCTIONS)")
print(f"  lean       {header + lean_prompt:>5}  ({header} header + {lean_prompt} lean prompt)\n")

print("== tools (exact wire JSON) ==")
for k, v in sorted(by.items(), key=lambda kv: -kv[1]):
    print(f"  {v:>5}  {k}{'   [KEEP]' if k in KEEP else '   culled'}")
print(f"  baseline total {base_tools}")
print(f"  lean total     {lean_tools}  (culled {sum(culled.values())}: "
      + ", ".join(culled) + ")\n")

b = instr_exact + base_tools
l = header + lean_prompt + lean_tools
print("== instr + tools (EXACT) ==")
print(f"  baseline {b}")
print(f"  lean     {l}")
print(f"  saving   {b - l}  ({100*(b-l)/b:.0f}%)\n")

PERM_BASE, PERM_LEAN = 815, 30   # file-size estimate; not in this dump
print("== + permission narrative (still estimated, not in dump) ==")
print(f"  full fixed/turn  baseline ~{b+PERM_BASE}   lean ~{l+PERM_LEAN}   "
      f"saving ~{(b+PERM_BASE)-(l+PERM_LEAN)} ({100*((b+PERM_BASE)-(l+PERM_LEAN))/(b+PERM_BASE):.0f}%)")
print("\nNote: dump is the offline gpt-5.2-codex config (fallback model metadata).")
print("Production tool flags may differ slightly; rerun the test on an authed host to confirm.")
