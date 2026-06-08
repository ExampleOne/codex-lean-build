import Mathlib

open MeasureTheory

/-!
# When can you swap integration and summation?

`∫ (∑ᵢ fᵢ) = ∑ᵢ (∫ fᵢ)` holds when each `fᵢ` is a.e. strongly measurable and the
total L¹ mass `∑ᵢ ∫ ‖fᵢ‖` is finite. The agent should replace `sorry` with a real
proof and leave the file building with no errors and no `sorry`.
-/

variable {ι α E : Type*} [Countable ι] [MeasurableSpace α] {μ : Measure α}
  [NormedAddCommGroup E] [NormedSpace ℝ E]

theorem sum_integral_swap {f : ι → α → E}
    (hf : ∀ i, AEStronglyMeasurable (f i) μ)
    (hf' : ∑' i, ∫⁻ a, ‖f i a‖₊ ∂μ ≠ ⊤) :
    ∫ a, ∑' i, f i a ∂μ = ∑' i, ∫ a, f i a ∂μ := by
  sorry
