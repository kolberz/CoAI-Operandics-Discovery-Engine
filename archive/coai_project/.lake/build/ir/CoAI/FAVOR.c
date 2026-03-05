// Lean compiler output
// Module: CoAI.FAVOR
// Imports: public import Init public import Mathlib.MeasureTheory.Integral.Bochner.Basic public import Mathlib.Probability.Notation public import Mathlib.Analysis.SpecialFunctions.Exponential public import Mathlib.Analysis.SpecialFunctions.Trigonometric.Basic public import Mathlib.Analysis.InnerProductSpace.Basic public import Mathlib.Data.Fin.Basic public import Mathlib.Tactic.Positivity public import CoAI.GaussianCharFun
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
uint8_t lean_nat_dec_eq(lean_object*, lean_object*);
lean_object* lean_nat_sub(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___redArg(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___redArg___boxed(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter(lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___boxed(lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___redArg(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; uint8_t x_5; 
x_4 = lean_unsigned_to_nat(0u);
x_5 = lean_nat_dec_eq(x_1, x_4);
if (x_5 == 1)
{
lean_object* x_6; lean_object* x_7; 
lean_dec(x_3);
x_6 = lean_box(0);
x_7 = lean_apply_1(x_2, x_6);
return x_7;
}
else
{
lean_object* x_8; lean_object* x_9; uint8_t x_10; lean_object* x_11; lean_object* x_12; 
lean_dec(x_2);
x_8 = lean_unsigned_to_nat(1u);
x_9 = lean_nat_sub(x_1, x_8);
x_10 = lean_nat_dec_eq(x_9, x_4);
lean_dec(x_9);
x_11 = lean_box(0);
x_12 = lean_apply_1(x_3, x_11);
return x_12;
}
}
}
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___redArg___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; 
x_4 = lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___redArg(x_1, x_2, x_3);
lean_dec(x_1);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
lean_object* x_5; 
x_5 = lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___redArg(x_2, x_3, x_4);
return x_5;
}
}
LEAN_EXPORT lean_object* lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
lean_object* x_5; 
x_5 = lp_coai___private_CoAI_FAVOR_0__StochasticAttention_FavorPhi_match__1_splitter(x_1, x_2, x_3, x_4);
lean_dec(x_2);
return x_5;
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_MeasureTheory_Integral_Bochner_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_Notation(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Analysis_SpecialFunctions_Exponential(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Analysis_SpecialFunctions_Trigonometric_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Analysis_InnerProductSpace_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Data_Fin_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Positivity(uint8_t builtin);
lean_object* initialize_coai_CoAI_GaussianCharFun(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_CoAI_FAVOR(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_MeasureTheory_Integral_Bochner_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_Notation(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Analysis_SpecialFunctions_Exponential(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Analysis_SpecialFunctions_Trigonometric_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Analysis_InnerProductSpace_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Data_Fin_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Positivity(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_GaussianCharFun(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
