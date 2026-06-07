#!/usr/bin/env python3
"""Estimate per-turn token overhead of Codex vs. the lean-formaliser build.

All numbers are derived from the actual source files in ../../codex-rs so the
estimate is reproducible. Tool-schema costs are estimated from the string
literals in each *_spec.rs (descriptions + enums dominate the serialized JSON);
we add a structural multiplier for JSON keys/braces.

Run:  /tmp/tkenv/bin/python token_estimate.py     (any python with tiktoken)
"""
import os
import re
import sys

try:
    import tiktoken
except ImportError:
    sys.exit("pip install tiktoken (e.g. in a venv) and re-run")

ENC = tiktoken.get_encoding("o200k_base")  # GPT-5.x / o-series tokenizer
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
RS = os.path.join(ROOT, "codex-rs")
LEAN_PROMPT = os.path.join(os.path.dirname(__file__), "..", "prompt", "lean_formaliser_prompt.md")

# JSON structure overhead on top of literal description/enum text.
JSON_OVERHEAD = 1.20


def tok(s):
    return len(ENC.encode(s))


def file_tok(path):
    with open(path) as f:
        return tok(f.read())


def spec_literal_tok(path):
    """Tokens of the string-literal content in a *_spec.rs file."""
    with open(path) as f:
        src = f.read()
    chunks = re.findall(r'r#"(.*?)"#', src, re.S)
    chunks += re.findall(r'r"(.*?)"', src, re.S)
    chunks += re.findall(r'"((?:[^"\\]|\\.){4,}?)"', src)
    return int(tok(" ".join(chunks)) * JSON_OVERHEAD)


def p(*a):
    return os.path.join(RS, *a)


# ---- system prompt -------------------------------------------------------
base_prompt = file_tok(p("models-manager", "prompt.md"))          # == default.md
lean_prompt = file_tok(LEAN_PROMPT)

# ---- tool schemas (model-visible) ---------------------------------------
SPECS = {
    "shell / exec":        ("core/src/tools/handlers/shell_spec.rs", True,  True),
    "apply_patch (tool)":  ("core/src/tools/handlers/apply_patch_spec.rs", True,  True),
    "update_plan":         ("core/src/tools/handlers/plan_spec.rs", True,  False),
    "view_image":          ("core/src/tools/handlers/view_image_spec.rs", True,  False),
    "request_user_input":  ("core/src/tools/handlers/request_user_input_spec.rs", False, False),
    "mcp_resource":        ("core/src/tools/handlers/mcp_resource_spec.rs", False, False),
    "tool_search":         ("core/src/tools/handlers/tool_search_spec.rs", False, False),
    "multi_agents":        ("core/src/tools/handlers/multi_agents_spec.rs", False, False),
    "agent_jobs":          ("core/src/tools/handlers/agent_jobs_spec.rs", False, False),
    "request_plugin_install": ("core/src/tools/handlers/request_plugin_install_spec.rs", False, False),
}
# tuple = (path, in_baseline_default_set, in_lean_set)

# apply_patch grammar instructions shipped in the prompt for codex models
apply_patch_instr = file_tok(p("prompts/templates/apply_patch_tool_instructions.md"))

# ---- per-turn permission / sandbox narrative ----------------------------
approval = file_tok(p("prompts/templates/permissions/approval_policy/on_request.md"))
sandbox = file_tok(p("prompts/templates/permissions/sandbox_mode/workspace_write.md"))

# =========================================================================
print(f"{'tokenizer':<28} o200k_base")
print(f"{'JSON structural overhead':<28} x{JSON_OVERHEAD}\n")

print("== SYSTEM PROMPT ==")
print(f"  baseline (prompt.md)        {base_prompt:>6}")
print(f"  lean formaliser prompt      {lean_prompt:>6}")
print(f"  saving                      {base_prompt - lean_prompt:>6}\n")

print("== TOOL SCHEMAS (est. from spec literals x overhead) ==")
base_tools = lean_tools = 0
for name, (path, in_base, in_lean) in SPECS.items():
    fp = p(path)
    if not os.path.exists(fp):
        print(f"  {name:<26} MISSING")
        continue
    t = spec_literal_tok(fp)
    b = t if in_base else 0
    l = t if in_lean else 0
    base_tools += b
    lean_tools += l
    flag = ("base" if in_base else "    ") + " " + ("lean" if in_lean else "    ")
    print(f"  {name:<26} {t:>6}   [{flag}]")
print(f"  apply_patch instr (prompt)  {apply_patch_instr:>6}   [base lean]  (kept, both)")
base_tools += apply_patch_instr
lean_tools += apply_patch_instr
print(f"  -> baseline tool payload    {base_tools:>6}")
print(f"  -> lean tool payload        {lean_tools:>6}")
print(f"  saving                      {base_tools - lean_tools:>6}\n")

print("== PERMISSION / SANDBOX NARRATIVE (per turn) ==")
base_perm = approval + sandbox
lean_perm = 30  # one hardcoded line
print(f"  baseline (on_request+sbx)   {base_perm:>6}")
print(f"  lean (one hardcoded line)   {lean_perm:>6}")
print(f"  saving                      {base_perm - lean_perm:>6}\n")

base_total = base_prompt + base_tools + base_perm
lean_total = lean_prompt + lean_tools + lean_perm
print("== FIXED PER-TURN OVERHEAD (input tokens, every turn) ==")
print(f"  baseline                    {base_total:>6}")
print(f"  lean                        {lean_total:>6}")
print(f"  saving / turn               {base_total - lean_total:>6}  "
      f"({100*(base_total-lean_total)/base_total:.0f}% reduction)\n")

for turns in (20, 50, 100):
    print(f"  over {turns:>3} turns: {(base_total-lean_total)*turns:>8} input tokens saved")
