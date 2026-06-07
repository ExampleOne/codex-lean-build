#!/usr/bin/env python3
"""Prototype: proof-tuned history compaction (drop superseded diagnostics).

In a proof-repair loop the agent re-checks the same file many times; each check's
diagnostics/goal output is appended to history and RE-SENT every subsequent turn.
Old diagnostics for a file are superseded the moment it is re-checked, yet they keep
billing as input tokens every turn — a quadratic cost.

This demonstrates the fix: keep only the LATEST tool output per file, replacing older
ones with a one-line stub. The intended integration point in codex-rs is
`context_manager/history.rs::for_prompt` (which already mutates FunctionCallOutput
history items — it strips images there), so this transform would run right before the
prompt is built, each turn.

Run:  /tmp/tkenv/bin/python compaction_prototype.py
"""
import tiktoken

ENC = tiktoken.get_encoding("o200k_base")
tok = lambda s: len(ENC.encode(s))

STUB = "[superseded diagnostics for {f} — file re-checked on a later turn]"

# A realistic per-check diagnostic block (~ what lean_diagnostic_messages / lake-quiet
# returns for a file mid-proof: an error + goal state).
def diag(f, n):
    return (f"{f}:{14+n}:3 error: unsolved goals\n"
            f"case inr\n p q : Prop\n h2 : q\n ⊢ q ∨ p\n"
            f"{f}:{20+n}:2 error: unknown identifier 'Nat.foo{n}'\n")


def simulate(turns, files):
    """Return list of (turn, file, output) — one tool output appended per turn."""
    return [(t, files[t % len(files)], diag(files[t % len(files)], t)) for t in range(turns)]


def cumulative_input_tokens(history_at_turn):
    """Sum of context size across all turns (history is re-sent every turn)."""
    return sum(tok(h) for h in history_at_turn)


def naive(transcript):
    """Full history retained; context at turn k = all outputs 0..k."""
    out, acc = [], []
    for _, _, o in transcript:
        acc.append(o)
        out.append("\n".join(acc))
    return out


def compacted(transcript):
    """Keep only the latest output per file; older -> stub. Context at turn k."""
    out = []
    seen_order = []          # list of (file, output) in insertion order, latest per file
    latest_turn = {}
    for k, (_, f, o) in enumerate(transcript):
        latest_turn[f] = k
        # rebuild: for each appended item up to k, stub it if a newer one for same file exists
        items = []
        for j, (_, fj, oj) in enumerate(transcript[:k + 1]):
            if j == latest_turn[fj]:
                items.append(oj)            # latest for its file -> keep full
            else:
                items.append(STUB.format(f=fj))
        out.append("\n".join(items))
    return out


def main():
    for turns, files in [(30, ["Foo.lean"]), (30, ["Foo.lean", "Bar.lean", "Baz.lean"])]:
        ts = simulate(turns, files)
        n = cumulative_input_tokens(naive(ts))
        c = cumulative_input_tokens(compacted(ts))
        label = f"{turns} turns, {len(files)} file(s)"
        print(f"== {label} ==")
        print(f"  naive cumulative input tokens (diagnostics only) : {n:>8}")
        print(f"  proof-compacted                                  : {c:>8}")
        print(f"  saving                                           : {n-c:>8}  ({100*(n-c)/n:.0f}%)")
        # final-turn context size (what the model carries at the end)
        print(f"  final-turn context: naive {tok(naive(ts)[-1]):>5}  compacted {tok(compacted(ts)[-1]):>5}\n")

    print("Only diagnostics are modelled here; in a real run reasoning + edits also")
    print("accumulate, but stale tool output is the largest re-sent component. Combine")
    print("with lake-quiet (per-output filter) and prompt caching (cheap fixed prefix).")


if __name__ == "__main__":
    main()
