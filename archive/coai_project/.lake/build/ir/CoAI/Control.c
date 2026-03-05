// Lean compiler output
// Module: CoAI.Control
// Imports: public import Init public import Mathlib.Probability.ProbabilityMassFunction.Basic public import Mathlib.Probability.ProbabilityMassFunction.Monad public import Mathlib.MeasureTheory.Measure.MeasureSpace public import Mathlib.MeasureTheory.Integral.Lebesgue.Markov public import Mathlib.Topology.Instances.ENNReal.Lemmas public import Mathlib.Tactic.Linarith public import Mathlib.Data.Real.Basic public import Mathlib.Probability.Martingale.Basic public import Mathlib.Probability.Process.Stopping public import Mathlib.Probability.Process.HittingTime public import Mathlib.Probability.Martingale.OptionalStopping
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
LEAN_EXPORT lean_object* lp_coai_CoAI_Control_instMeasurableSpace__coAI(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Control_instMeasurableSpace__coAI(lean_object* x_1) {
_start:
{
lean_object* x_2; 
x_2 = lean_box(0);
return x_2;
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Monad(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_MeasureTheory_Measure_MeasureSpace(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_MeasureTheory_Integral_Lebesgue_Markov(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Topology_Instances_ENNReal_Lemmas(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Linarith(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Data_Real_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_Martingale_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_Process_Stopping(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_Process_HittingTime(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_Martingale_OptionalStopping(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_CoAI_Control(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
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
res = initialize_mathlib_Mathlib_MeasureTheory_Integral_Lebesgue_Markov(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Topology_Instances_ENNReal_Lemmas(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Linarith(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Data_Real_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_Martingale_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_Process_Stopping(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_Process_HittingTime(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_Martingale_OptionalStopping(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
