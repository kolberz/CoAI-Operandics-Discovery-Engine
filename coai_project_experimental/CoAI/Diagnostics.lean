import CoAI.FavorSubGaussian
import CoAI.Concentration
import CoAI.CertifiedStack

set_option pp.universes true
set_option pp.all true

open MeasureTheory ProbabilityTheory

namespace Diagnostics

-- Check universe levels and lemma types
#check CoAI.SubGaussian.abs_tail
#check HasSubgaussianMGF.measure_ge_le
#check Measure.real

-- Check KernelError_m
#check StochasticAttention.KernelError_m
variable {Ω : Type*} [MeasureSpace Ω] [IsProbabilityMeasure (volume : Measure Ω)]
variable {E : Type*} [NormedAddCommGroup E] [InnerProductSpace ℝ E]
variable (m : ℕ) (ω : Ω → Fin m → E) (q k : E)
#check StochasticAttention.KernelError_m (m := m) (ω := ω) q k

end Diagnostics
