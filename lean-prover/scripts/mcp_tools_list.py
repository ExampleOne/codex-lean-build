#!/usr/bin/env python3
"""Enumerate the tools an MCP server actually exposes, with their token cost.

Reality-checks the lean-lsp-mcp tool surface against the lean build's config: tool
names drift across versions, and LEAN_MCP_DISABLED_TOOLS is a DENY list, so the
exposed set is "everything the installed server has minus the deny list". Run this
after upgrading lean-lsp-mcp to refresh `[lean_lsp].all` in lean-prover.toml.

Usage:
    python mcp_tools_list.py <lean_project_dir> [--disabled a,b,c]

Needs `uvx` and a Lean toolchain on PATH. Token counts need tiktoken (optional).
"""
import json, os, subprocess, sys, time

def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    proj = os.path.abspath(sys.argv[1])
    disabled = ""
    if "--disabled" in sys.argv:
        disabled = sys.argv[sys.argv.index("--disabled") + 1]

    try:
        import tiktoken
        enc = tiktoken.get_encoding("o200k_base")
        tok = lambda o: len(enc.encode(json.dumps(o)))
    except Exception:
        tok = None

    env = dict(os.environ)
    env["LEAN_PROJECT_PATH"] = proj
    if disabled:
        env["LEAN_MCP_DISABLED_TOOLS"] = disabled

    p = subprocess.Popen(["uvx", "lean-lsp-mcp"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, bufsize=0)
    s = lambda o: (p.stdin.write((json.dumps(o) + "\n").encode()), p.stdin.flush())
    s({"jsonrpc": "2.0", "id": 1, "method": "initialize",
       "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                  "clientInfo": {"name": "probe", "version": "0"}}})
    s({"jsonrpc": "2.0", "method": "notifications/initialized"})
    s({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    deadline = time.monotonic() + 120
    tools = None
    while time.monotonic() < deadline:
        line = p.stdout.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if msg.get("id") == 2 and "result" in msg:
            tools = msg["result"]["tools"]
            break
    p.terminate()

    if tools is None:
        sys.exit("no tools/list response")
    total = 0
    print(f"{len(tools)} tools exposed" + (f" (deny: {disabled})" if disabled else "") + ":")
    for t in sorted(tools, key=lambda x: x["name"]):
        if tok:
            c = tok(t); total += c
            print(f"  {c:>4} tok  {t['name']}")
        else:
            print(f"  {t['name']}")
    if tok:
        print(f"  -------- {total} tok total (per-turn cost if exposed directly)")

if __name__ == "__main__":
    main()
