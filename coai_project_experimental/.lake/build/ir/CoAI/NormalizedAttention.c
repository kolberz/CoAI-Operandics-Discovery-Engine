// Lean compiler output
// Module: CoAI.NormalizedAttention
// Imports: public import Init public import Mathlib.Analysis.InnerProductSpace.Basic public import Mathlib.MeasureTheory.Measure.ProbabilityMeasure public import Mathlib.Tactic.Positivity public import Mathlib.Tactic.FieldSimp public import Mathlib.Tactic.Linarith public import CoAI.Concentration
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
lean_object* initialize_mathlib_Mathlib_Analysis_InnerProductSpace_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_MeasureTheory_Measure_ProbabilityMeasure(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Positivity(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_FieldSimp(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Linarith(uint8_t builtin);
lean_object* initialize_coai_CoAI_Concentration(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_CoAI_NormalizedAttention(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Analysis_InnerProductSpace_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_MeasureTheory_Measure_ProbabilityMeasure(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Positivity(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_FieldSimp(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Linarith(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_Concentration(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
