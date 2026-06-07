#!/usr/bin/env python3
"""Benchmark: Lean LSP inner-loop tokens vs `lake-quiet build` (+ grep).

Compares the three mechanisms where an LSP changes token cost in a proof loop:
  S1  single-file error feedback   (lake build output      vs LSP diagnostics)
  S2  lemma discovery              (grep Mathlib            vs LSP/exact? search)
  S3  recheck in a big project     (lake rebuild progress   vs LSP diagnostics)

By default it tokenizes the bundled representative samples (real Lean-LSP /
lake-output message shapes; reconstructed, NOT a live capture on this host because
the toolchain install was blocked). With a live toolchain you can regenerate S1
for real:  python bench.py --live <project_root> <file.lean>

Run:  /tmp/tkenv/bin/python bench.py
"""
import os
import shutil
import subprocess
import sys

import tiktoken

ENC = tiktoken.get_encoding("o200k_base")
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "samples")


def tok(s):
    return len(ENC.encode(s))


def read(name):
    with open(os.path.join(S, name)) as f:
        return f.read()


def lake_quiet_filter(raw):
    """Same filter as scripts/lake-quiet, in Python, for apples-to-apples."""
    import re
    out, seen, blank = [], set(), False
    drop = re.compile(r'^(Building |Compiling |info: downloading|Computing build jobs|\[[0-9]+/[0-9]+\])')
    for line in raw.splitlines():
        line = re.sub(r'\x1b\[[0-9;]*[mK]', '', line)
        if drop.match(line):
            continue
        if not line.strip():
            if blank:
                continue
            blank = True
        else:
            blank = False
        if line not in seen or line.strip() == "":
            seen.add(line)
            out.append(line)
    return "\n".join(out)


def big_project_lake_build(n_deps=400):
    """Realistic `lake build` output when rechecking one clean file in a project
    that imports Mathlib: hundreds of dependency progress lines, no errors."""
    lines = ["info: [0/%d] Computing build jobs" % (n_deps + 1)]
    mods = ["Init", "Logic.Basic", "Data.Nat.Basic", "Data.List.Basic", "Algebra.Group.Defs",
            "Algebra.Group.Basic", "Order.Basic", "Data.Set.Basic", "Topology.Basic",
            "Analysis.Normed.Group.Basic"]
    for i in range(n_deps):
        lines.append(f"[{i+1}/{n_deps+1}] Building Mathlib.{mods[i % len(mods)]}")
    lines.append(f"[{n_deps+1}/{n_deps+1}] Building MyProject.Target")
    return "\n".join(lines) + "\n"


def row(name, before_label, before, after_label, after):
    b, a = tok(before), tok(after)
    cut = 100 * (b - a) / b if b else 0
    return (name, before_label, b, after_label, a, cut)


def main():
    # Three columns per scenario: raw stock output, our lake-quiet wrapper, the LSP.
    s1_raw = read("s1_lake_build.txt")
    s3_raw = big_project_lake_build()
    scenarios = [
        ("S1 error feedback",  s1_raw,                       read("s1_lsp_diag.txt")),
        ("S2 lemma search",    read("s2_grep_mathlib.txt"),  read("s2_lsp_search.txt")),
        ("S3 recheck (clean)", s3_raw,                       "Target.lean: ok (0 diagnostics)"),
    ]
    # S2's "raw" is grep, which lake-quiet does not touch -> quiet == raw there.
    no_quiet = {"S2 lemma search"}

    print("Mechanism             raw     lake-quiet      LSP    quiet vs raw   LSP vs quiet")
    print("-" * 80)
    tot_raw = tot_q = tot_l = 0
    for name, raw, lsp in scenarios:
        r = tok(raw)
        q = r if name in no_quiet else tok(lake_quiet_filter(raw))
        l = tok(lsp)
        tot_raw += r; tot_q += q; tot_l += l
        qvr = 100 * (r - q) / r if r else 0
        lvq = 100 * (q - l) / q if q else 0
        print(f"{name:<18} {r:>6}      {q:>6}      {l:>6}      {qvr:>5.0f}%        {lvq:>5.0f}%")
    print("-" * 80)
    print(f"{'TOTAL':<18} {tot_raw:>6}      {tot_q:>6}      {tot_l:>6}      "
          f"{100*(tot_raw-tot_q)/tot_raw:>5.0f}%        {100*(tot_q-tot_l)/tot_q:>5.0f}%")
    print("\nReading: `lake-quiet` already removes build-progress noise (S1/S3), so the LSP")
    print("adds little there. The LSP's distinctive, additive win is S2 (lemma discovery),")
    print("which lake-quiet cannot help with — plus incremental checking that cuts turns.")
    print("\nSamples are representative (real Lean-LSP/lake message shapes), reconstructed —")
    print("not a live capture (toolchain install was blocked). Regenerate live with --live.")

    if len(sys.argv) >= 4 and sys.argv[1] == "--live":
        run_live(sys.argv[2], sys.argv[3])


def run_live(root, file):
    if not shutil.which("lake"):
        print("\n[--live] no `lake` on PATH; skipping live run.")
        return
    print("\n== LIVE ==")
    raw = subprocess.run(["lake", "build"], cwd=root, capture_output=True, text=True)
    raw_out = raw.stdout + raw.stderr
    lsp = subprocess.run(
        [sys.executable, os.path.join(HERE, "lean_lsp_client.py"), root, file],
        capture_output=True, text=True).stdout
    print(f"live lake-quiet : {tok(lake_quiet_filter(raw_out)):>6} tok")
    print(f"live LSP diag   : {tok(lsp):>6} tok")


if __name__ == "__main__":
    main()
