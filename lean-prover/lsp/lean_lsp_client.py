#!/usr/bin/env python3
"""Thin Lean 4 LSP client — token-efficient diagnostics & goal state for an agent.

Speaks JSON-RPC over stdio to the Lean server (`lake serve`) and emits ONLY what a
formaliser needs: diagnostics (with their embedded goal state) and, on request, the
tactic goal at a cursor. No build progress, no file lists, no ANSI — none of the
noise that `lake build` (even filtered) carries.

This is the inner-loop replacement for `lake build` + `grep`:
    diagnostics(file)        -> errors/warnings/sorries with goal state, structured
    goal(file, line, col)    -> the exact tactic goal ($/lean/plainGoal)

Live usage (requires a Lean toolchain on PATH):
    python lean_lsp_client.py <project_root> <file.lean> [line col]

Design notes:
- Lean streams `$/lean/fileProgress`; diagnostics are only final once progress for
  the file is empty. We wait for that before reporting (bounded by --timeout).
- Stdlib only. One reader thread demuxes responses (by id) from notifications.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


class LeanLSP:
    def __init__(self, project_root, timeout=60):
        self.root = Path(project_root).resolve()
        self.timeout = timeout
        self.proc = subprocess.Popen(
            ["lake", "serve"],
            cwd=str(self.root),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self._id = 0
        self._resp = {}
        self._diags = {}          # uri -> list[diagnostic]
        self._progress_done = {}  # uri -> bool
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    # ---- wire framing ----
    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        self.proc.stdin.flush()

    def _read_loop(self):
        f = self.proc.stdout
        while True:
            header = b""
            while b"\r\n\r\n" not in header:
                chunk = f.read(1)
                if not chunk:
                    return
                header += chunk
            length = int(dict(
                line.split(": ", 1) for line in
                header.decode().strip().split("\r\n")
            )["Content-Length"])
            body = f.read(length)
            try:
                msg = json.loads(body)
            except Exception:
                continue
            with self._lock:
                if "id" in msg and ("result" in msg or "error" in msg):
                    self._resp[msg["id"]] = msg
                elif msg.get("method") == "textDocument/publishDiagnostics":
                    p = msg["params"]
                    self._diags[p["uri"]] = p["diagnostics"]
                elif msg.get("method") == "$/lean/fileProgress":
                    p = msg["params"]
                    self._progress_done[p["textDocument"]["uri"]] = \
                        len(p.get("processing", [])) == 0

    def _request(self, method, params):
        with self._lock:
            self._id += 1
            rid = self._id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            with self._lock:
                if rid in self._resp:
                    return self._resp.pop(rid)
            time.sleep(0.01)
        raise TimeoutError(method)

    def _notify(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    # ---- protocol ----
    def initialize(self):
        self._request("initialize", {
            "processId": os.getpid(),
            "rootUri": self.root.as_uri(),
            "capabilities": {},
        })
        self._notify("initialized", {})

    def _uri(self, file):
        return (self.root / file).resolve().as_uri()

    def open(self, file):
        uri = self._uri(file)
        text = (self.root / file).read_text()
        self._progress_done[uri] = False
        self._notify("textDocument/didOpen", {"textDocument": {
            "uri": uri, "languageId": "lean", "version": 1, "text": text}})
        return uri

    def wait_ready(self, uri):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self._progress_done.get(uri):
                    return
            time.sleep(0.05)

    def diagnostics(self, uri):
        with self._lock:
            return self._diags.get(uri, [])

    def plain_goal(self, uri, line, col):
        r = self._request("$/lean/plainGoal",
                          {"textDocument": {"uri": uri},
                           "position": {"line": line, "character": col}})
        return r.get("result")

    def close(self):
        try:
            self._request("shutdown", {})
            self._notify("exit", {})
        except Exception:
            pass
        self.proc.terminate()


def render_diagnostics(file, diags):
    """Compact, token-minimal rendering — the only thing the agent sees."""
    if not diags:
        return f"{file}: ok (0 diagnostics)"
    out = []
    for d in diags:
        sev = {1: "error", 2: "warning", 3: "info", 4: "hint"}.get(d.get("severity"), "note")
        ln = d["range"]["start"]["line"] + 1
        ch = d["range"]["start"]["character"] + 1
        out.append(f"{file}:{ln}:{ch} {sev}: {d['message'].strip()}")
    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: lean_lsp_client.py <project_root> <file.lean> [line col]")
    root, file = sys.argv[1], sys.argv[2]
    lsp = LeanLSP(root)
    try:
        lsp.initialize()
        uri = lsp.open(file)
        lsp.wait_ready(uri)
        print(render_diagnostics(file, lsp.diagnostics(uri)))
        if len(sys.argv) == 5:
            line, col = int(sys.argv[3]) - 1, int(sys.argv[4]) - 1
            goal = lsp.plain_goal(uri, line, col)
            if goal and goal.get("goals"):
                print("\n-- goal --\n" + "\n".join(goal["goals"]))
    finally:
        lsp.close()


if __name__ == "__main__":
    main()
