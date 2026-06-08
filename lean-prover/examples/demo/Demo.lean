-- Small, no-Mathlib smoke test for codex-lean.
-- Each theorem is provable in plain Lean 4 core; the agent should replace every
-- `sorry` with a real proof and leave the file building cleanly.

theorem add_comm_nat (n m : Nat) : n + m = m + n := by
  sorry

theorem reverse_reverse {α : Type} (xs : List α) : xs.reverse.reverse = xs := by
  sorry
