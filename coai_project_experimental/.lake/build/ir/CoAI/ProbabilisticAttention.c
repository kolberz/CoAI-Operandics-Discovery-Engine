// Lean compiler output
// Module: CoAI.ProbabilisticAttention
// Imports: public import Init public import Mathlib.MeasureTheory.Integral.Bochner.Basic public import Mathlib.Tactic.Positivity public import Mathlib.Data.Matrix.Basic
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
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__0(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__1(lean_object*, lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib_Matrix_transpose___redArg(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__2(lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib_dotProduct___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__3(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__3___boxed(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib___private_Mathlib_Data_Real_Basic_0__Real_mul(lean_object*, lean_object*);
static const lean_closure_object lp_coai_StochasticAttention_AttnKernelQuad___redArg___closed__0_value = {.m_header = {.m_rc = 0, .m_cs_sz = sizeof(lean_closure_object) + sizeof(void*)*0, .m_other = 0, .m_tag = 245}, .m_fun = (void*)lp_mathlib___private_Mathlib_Data_Real_Basic_0__Real_mul, .m_arity = 2, .m_num_fixed = 0, .m_objs = {} };
static const lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___closed__0 = (const lean_object*)&lp_coai_StochasticAttention_AttnKernelQuad___redArg___closed__0_value;
extern lean_object* lp_mathlib_Real_instAddCommMonoid;
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__2(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__0(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__0___boxed(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__0(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; 
x_4 = lean_apply_2(x_1, x_3, x_2);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__1(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
lean_object* x_5; 
x_5 = lean_apply_3(x_1, x_2, x_3, x_4);
return x_5;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__2(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; 
x_4 = lp_mathlib_Matrix_transpose___redArg(x_1, x_3, x_2);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__3(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; lean_object* x_8; 
x_7 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__2), 3, 2);
lean_closure_set(x_7, 0, x_1);
lean_closure_set(x_7, 1, x_6);
x_8 = lp_mathlib_dotProduct___redArg(x_2, x_3, x_4, x_5, x_7);
return x_8;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__3___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; 
x_7 = lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__3(x_1, x_2, x_3, x_4, x_5, x_6);
lean_dec_ref(x_4);
return x_7;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad___redArg(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9) {
_start:
{
lean_object* x_10; lean_object* x_11; lean_object* x_12; lean_object* x_13; lean_object* x_14; lean_object* x_15; lean_object* x_16; 
x_10 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__0), 3, 2);
lean_closure_set(x_10, 0, x_7);
lean_closure_set(x_10, 1, x_9);
x_11 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__1), 4, 3);
lean_closure_set(x_11, 0, x_3);
lean_closure_set(x_11, 1, x_5);
lean_closure_set(x_11, 2, x_8);
x_12 = ((lean_object*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___closed__0));
x_13 = lp_mathlib_Real_instAddCommMonoid;
x_14 = lean_apply_1(x_4, x_6);
x_15 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__3___boxed), 6, 5);
lean_closure_set(x_15, 0, x_14);
lean_closure_set(x_15, 1, x_2);
lean_closure_set(x_15, 2, x_12);
lean_closure_set(x_15, 3, x_13);
lean_closure_set(x_15, 4, x_11);
x_16 = lp_mathlib_dotProduct___redArg(x_1, x_12, x_13, x_15, x_10);
return x_16;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelQuad(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9, lean_object* x_10, lean_object* x_11, lean_object* x_12, lean_object* x_13) {
_start:
{
lean_object* x_14; 
x_14 = lp_coai_StochasticAttention_AttnKernelQuad___redArg(x_5, x_6, x_7, x_8, x_9, x_10, x_11, x_12, x_13);
return x_14;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__2(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; 
x_4 = lp_mathlib_Matrix_transpose___redArg(x_1, x_2, x_3);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__0(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; lean_object* x_8; 
x_7 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__2), 3, 2);
lean_closure_set(x_7, 0, x_1);
lean_closure_set(x_7, 1, x_6);
x_8 = lp_mathlib_dotProduct___redArg(x_2, x_3, x_4, x_7, x_5);
return x_8;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__0___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; 
x_7 = lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__0(x_1, x_2, x_3, x_4, x_5, x_6);
lean_dec_ref(x_4);
return x_7;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin___redArg(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9) {
_start:
{
lean_object* x_10; lean_object* x_11; lean_object* x_12; lean_object* x_13; lean_object* x_14; lean_object* x_15; lean_object* x_16; 
x_10 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__0), 3, 2);
lean_closure_set(x_10, 0, x_7);
lean_closure_set(x_10, 1, x_9);
x_11 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___lam__1), 4, 3);
lean_closure_set(x_11, 0, x_3);
lean_closure_set(x_11, 1, x_5);
lean_closure_set(x_11, 2, x_8);
x_12 = ((lean_object*)(lp_coai_StochasticAttention_AttnKernelQuad___redArg___closed__0));
x_13 = lp_mathlib_Real_instAddCommMonoid;
x_14 = lean_apply_1(x_4, x_6);
x_15 = lean_alloc_closure((void*)(lp_coai_StochasticAttention_AttnKernelLin___redArg___lam__0___boxed), 6, 5);
lean_closure_set(x_15, 0, x_14);
lean_closure_set(x_15, 1, x_1);
lean_closure_set(x_15, 2, x_12);
lean_closure_set(x_15, 3, x_13);
lean_closure_set(x_15, 4, x_10);
x_16 = lp_mathlib_dotProduct___redArg(x_2, x_12, x_13, x_11, x_15);
return x_16;
}
}
LEAN_EXPORT lean_object* lp_coai_StochasticAttention_AttnKernelLin(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9, lean_object* x_10, lean_object* x_11, lean_object* x_12, lean_object* x_13) {
_start:
{
lean_object* x_14; 
x_14 = lp_coai_StochasticAttention_AttnKernelLin___redArg(x_5, x_6, x_7, x_8, x_9, x_10, x_11, x_12, x_13);
return x_14;
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_MeasureTheory_Integral_Bochner_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Positivity(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Data_Matrix_Basic(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_CoAI_ProbabilisticAttention(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_MeasureTheory_Integral_Bochner_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Positivity(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Data_Matrix_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
