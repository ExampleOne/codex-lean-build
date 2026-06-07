#!/usr/bin/env python3
"""Generate patches/config.toml (Codex runtime config) from lean-prover.toml.

Single source of truth: edit lean-prover.toml, run this (or ./build.sh). The output
is consumed by run.sh, which copies it into the isolated CODEX_HOME.
"""
import os
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "..", "lean-prover.toml")
OUT = os.path.join(HERE, "..", "patches", "config.toml")


def main():
    with open(MANIFEST, "rb") as f:
        cfg = tomllib.load(f)

    model = cfg["model"]["slug"]
    rt = cfg["runtime"]
    lsp = cfg.get("lean_lsp", {})
    cull = cfg.get("cull", {})

    lines = [
        "# GENERATED from lean-prover.toml by scripts/gen_config.py — do not edit by hand.",
        "# Drop into $CODEX_HOME/config.toml (run.sh does this automatically).",
        "",
        f'model = "{model}"',
        f'approval_policy = "{rt["approval_policy"]}"',
        f'sandbox_mode = "{rt["sandbox_mode"]}"',
        f'web_search = "{rt["web_search"]}"',
        "",
        "[tools]",
        "web_search = false",
        "view_image = false",
        f'experimental_request_user_input = {{ enabled = {str(rt["request_user_input"]).lower()} }}',
    ]

    if lsp.get("enabled"):
        disabled = [t for t in lsp.get("all", []) if t not in lsp.get("keep", [])]
        keep = lsp.get("keep", [])
        # Sanity check: direct exposure of many tools while tool_search is culled is costly.
        if cull.get("tool_search", False) and len(keep) > 6:
            print(f"WARNING: tool_search is culled but {len(keep)} lean-lsp tools are kept "
                  "(all exposed directly). Consider cull.tool_search=false to defer schemas.",
                  file=sys.stderr)
        args = ", ".join(f'"{a}"' for a in lsp["args"])
        lines += [
            "",
            "# --- lean-lsp-mcp (structured goal/diagnostics + lemma search) ---",
            f"# Exposes only: {', '.join(keep)}",
            "[mcp_servers.lean-lsp]",
            f'command = "{lsp["command"]}"',
            f"args = [{args}]",
            f'startup_timeout_sec = {lsp["startup_timeout_sec"]}',
            f'tool_timeout_sec = {lsp["tool_timeout_sec"]}',
            "[mcp_servers.lean-lsp.env]",
            f'LEAN_PROJECT_PATH = "{lsp["project_path"]}"',
            f'LEAN_MCP_DISABLED_TOOLS = "{",".join(disabled)}"',
        ]

    with open(OUT, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[gen] wrote {os.path.relpath(OUT)} from lean-prover.toml")


if __name__ == "__main__":
    main()
