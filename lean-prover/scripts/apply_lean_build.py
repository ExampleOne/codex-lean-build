#!/usr/bin/env python3
"""Apply the lean-formaliser optimisations to a Codex `codex-rs` checkout.

Compile-time changes are driven by ../lean-prover.toml ([prompt] + [cull]); runtime
config is handled separately by gen_config.py. Every edit is anchored to a unique
string and asserts the anchor exists, so the patcher fails loudly rather than
silently corrupting source if upstream moves.

Usage:
    python apply_lean_build.py <path-to-codex-rs>

Idempotent: re-running on an already-patched tree is a no-op (anchors gone -> skip).
"""
import os
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "lean-prover.toml")

# Anchored edits for each compile-time cull, keyed by the [cull] flag name.
# The culled handlers are bound to `_` / forced-early-return rather than deleted,
# so their imports stay used and the build stays warning-clean.
CULL_PATCHES = {
    "update_plan": (
        "core/src/tools/spec_plan.rs",
        "    planned_tools.add(PlanHandler);\n",
        "    let _ = PlanHandler; // [lean] update_plan not exposed to the model\n",
        True,
    ),
    "view_image": (
        "core/src/tools/spec_plan.rs",
        "        planned_tools.add(ViewImageHandler::new(ViewImageToolOptions {",
        "        let _ = (ViewImageHandler::new(ViewImageToolOptions { // [lean] view_image not exposed",
        True,
    ),
    "tool_search": (
        "core/src/tools/spec_plan.rs",
        "    if !(search_tool_enabled(turn_context) && namespace_tools_enabled(turn_context)) {",
        "    if true /* [lean] tool_search never exposed */ "
        "|| !(search_tool_enabled(turn_context) && namespace_tools_enabled(turn_context)) {",
        True,
    ),
}


def load_manifest():
    with open(MANIFEST, "rb") as f:
        return tomllib.load(f)


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

    cfg = load_manifest()

    # 1. System prompt (biggest win): swap both copies of the base instructions.
    prompt_file = os.path.join(HERE, "..", cfg["prompt"]["file"])
    lean = open(prompt_file).read()
    print(f"[prompt] source: {cfg['prompt']['file']}")
    replace_file(os.path.join(rs, "models-manager", "prompt.md"), lean,
                 "models-manager/prompt.md (BASE_INSTRUCTIONS)")
    replace_file(os.path.join(rs, "protocol", "src", "prompts", "base_instructions", "default.md"),
                 lean, "base_instructions/default.md")

    # 2. Tool culls — apply only the ones enabled in [cull].
    cull = cfg.get("cull", {})
    for name, (rel, old, new, required) in CULL_PATCHES.items():
        if cull.get(name, False):
            patch(os.path.join(rs, rel), old, new, f"cull {name}", required)
        else:
            print(f"[keep ] {name} (cull disabled in lean-prover.toml)")

    print("\nDone. Runtime config: run scripts/gen_config.py (or ./build.sh, which does both).")
    print("Then build:  (cd %s && cargo build --release -p codex-cli --bin codex)" % rs)


if __name__ == "__main__":
    main()
