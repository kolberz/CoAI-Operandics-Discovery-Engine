// Lean compiler output
// Module: CoAI.Composition
// Imports: public import Init public import CoAI.Substrate public import Mathlib.Probability.ProbabilityMassFunction.Basic public import Mathlib.Probability.ProbabilityMassFunction.Monad public import Mathlib.MeasureTheory.Measure.MeasureSpace public import Mathlib.Topology.Instances.ENNReal.Lemmas public import Mathlib.Topology.Algebra.InfiniteSum.ENNReal public import Mathlib.Tactic.Linarith public import Mathlib.Tactic.Ring
#include <lean/lean.h>
#if defined(__clang__)
#pragma clang diagnostic ignored "-Wunused-parameter"
#pragma clang diagnostic ignored "-Wunused-label"
#elif defined(__GNUC__) && !defined(__CLANG__)
#pragma GCC diagnostic ignored "-Wunused-parameter"
#pragma GCC diagnostic ignored "-Wunused-label"
#pragma GCC diagnostic ignored "-Wunused-but-set-variable"
#endif
#ifdef __cplusplus
extern "C" {
#endif
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_coai_CoAI_Substrate(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Monad(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_MeasureTheory_Measure_MeasureSpace(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Topology_Instances_ENNReal_Lemmas(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Topology_Algebra_InfiniteSum_ENNReal(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Linarith(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Ring(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_CoAI_Composition(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_Substrate(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Monad(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_MeasureTheory_Measure_MeasureSpace(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Topology_Instances_ENNReal_Lemmas(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Topology_Algebra_InfiniteSum_ENNReal(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Linarith(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Ring(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
