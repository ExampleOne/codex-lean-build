# Example: swapping integration and summation

A turnkey task for `codex-lean`: prove `∫ (∑ᵢ fᵢ) = ∑ᵢ (∫ fᵢ)`.

## The math
The interchange holds when **each `fᵢ` is a.e. strongly measurable** and the
**total L¹ mass `∑ᵢ ∫ ‖fᵢ‖` is finite** (`≠ ∞`). In Mathlib this is exactly
**`MeasureTheory.integral_tsum`**, so `sum_integral_swap` is dischargeable by
`exact integral_tsum hf hf'` (the agent should find it via `lean_leansearch` /
`lean_state_search`). If the Mathlib version uses `‖·‖ₑ` (enorm) rather than `‖·‖₊`,
the agent adjusts the hypothesis to match.

## Run it (requires Mathlib — a multi-GB cache)
```bash
# 1. toolchain + Mathlib cache (matches Mathlib's pinned lean-toolchain)
cd lean-prover/examples/sum-integral-swap
lake update                       # writes lean-toolchain + manifest from Mathlib
lake exe cache get                # downloads prebuilt Mathlib oleans (~5 GB)
lake build                        # should compile with the `sorry`

# 2. let codex-lean prove it (lean-lsp-mcp needs uvx on PATH)
LEAN_PROJECT_PATH="$PWD" \
  ../../run.sh exec "Prove sum_integral_swap in SumIntegralSwap.lean. Replace the \
sorry with a real proof; the interchange of sum and integral holds when each term is \
a.e. strongly measurable and the total L1 mass is finite."
```

> Note: `lake exe cache get` over a throttling VPN is the bottleneck (thousands of
> files). On an unthrottled network it's a few minutes. The `demo/` example needs no
> Mathlib and is the fast way to smoke-test the binary.
