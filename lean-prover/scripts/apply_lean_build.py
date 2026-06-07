#!/usr/bin/env python3
"""Apply the lean-formaliser optimisations to a Codex `codex-rs` checkout.

Every edit is anchored to a unique string and asserts the anchor exists, so the
patcher fails loudly rather than silently corrupting source if upstream moves.

Usage:
    python apply_lean_build.py <path-to-codex-rs>

Idempotent: re-running on an already-patched tree is a no-op (anchors gone -> skip).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEAN_PROMPT = os.path.join(HERE, "..", "prompt", "lean_formaliser_prompt.md")


def replace_file(path, content, label):
    with open(path, "w") as f:
        f.write(content)
    print(f"[prompt] wrote {label}: {path}")


def patch(path, old, new, label, required=True):
    with open(path) as f:
        src = f.read()
    if new in src and old not in src:
        print(f"[skip ] {label} (already applied)")
        return
    if old not in src:
        msg = f"[ERROR] anchor not found for {label} in {path}"
        if required:
            sys.exit(msg)
        print(msg + " (optional, skipped)")
        return
    with open(path, "w") as f:
        f.write(src.replace(old, new, 1))
    print(f"[patch] {label}")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    rs = os.path.abspath(sys.argv[1])
    if not os.path.isdir(os.path.join(rs, "core", "src")):
        sys.exit(f"not a codex-rs checkout: {rs}")

    lean = open(LEAN_PROMPT).read()

    # 1. System prompt (biggest win): swap both copies of the base instructions.
    replace_file(os.path.join(rs, "models-manager", "prompt.md"), lean,
                 "models-manager/prompt.md (BASE_INSTRUCTIONS)")
    replace_file(os.path.join(rs, "protocol", "src", "prompts", "base_instructions", "default.md"),
                 lean, "base_instructions/default.md")

    # 2. Cull tools the formaliser never uses: update_plan + view_image.
    #    We bind to `_` instead of deleting the `.add(...)` call, so the handler
    #    imports stay "used" (no unused-import warnings / clippy failures). The
    #    handler is constructed but never registered -> not in the registry and
    #    never sent to the model, which is the whole point.
    spec = os.path.join(rs, "core", "src", "tools", "spec_plan.rs")
    patch(spec,
          "    planned_tools.add(PlanHandler);\n",
          "    let _ = PlanHandler; // [lean] update_plan not exposed to the model\n",
          "drop update_plan from model-visible tools")
    patch(spec,
          "        planned_tools.add(ViewImageHandler::new(ViewImageToolOptions {",
          "        let _ = (ViewImageHandler::new(ViewImageToolOptions { // [lean] view_image not exposed",
          "drop view_image from model-visible tools")
    # tool_search (~193 tok, revealed by the real wire dump) — force the early return.
    patch(spec,
          "    if !(search_tool_enabled(turn_context) && namespace_tools_enabled(turn_context)) {",
          "    if true /* [lean] tool_search never exposed */ "
          "|| !(search_tool_enabled(turn_context) && namespace_tools_enabled(turn_context)) {",
          "drop tool_search from model-visible tools")

    print("\nDone. Build with:  (cd %s && cargo build --release -p codex-cli --bin codex)" % rs)
    print("Note: also disable web_search/MCP/multi-agent via config (see patches/config.toml).")


if __name__ == "__main__":
    main()
