// Lean compiler output
// Module: CoAI.LinearRouting
// Imports: public import Init public import Mathlib.Data.Matrix.Basic
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
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__0(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__1(lean_object*, lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib_Matrix_transpose___redArg(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__2(lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib_dotProduct___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__3(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__3___boxed(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib_CommRing_toNonUnitalCommRing___redArg(lean_object*);
lean_object* lp_mathlib_NonUnitalNonAssocRing_toNonUnitalNonAssocSemiring___redArg(lean_object*);
lean_object* lp_mathlib_NonUnitalNonAssocSemiring_toDistrib___redArg(lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg___lam__2(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg___lam__0(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg___lam__0___boxed(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_OuterN___redArg___lam__0(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib_Finset_sum___redArg(lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_OuterN___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_OuterN(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
lean_object* lp_mathlib_Field_toDivisionRing___redArg(lean_object*);
lean_object* lp_mathlib_Ring_toAddGroupWithOne___redArg(lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_ones___redArg(lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_ones(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_ones___boxed(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
lean_object* lean_nat_mod(lean_object*, lean_object*);
static lean_object* lp_coai_KernelAttention_Normalize___redArg___closed__0;
lean_object* lp_mathlib_DivisionRing_toDivInvMonoid___redArg(lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_Normalize___redArg(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_Normalize(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__0(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; 
x_4 = lean_apply_2(x_1, x_3, x_2);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__1(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
lean_object* x_5; 
x_5 = lean_apply_3(x_1, x_2, x_3, x_4);
return x_5;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__2(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; 
x_4 = lp_mathlib_Matrix_transpose___redArg(x_1, x_3, x_2);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__3(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; lean_object* x_8; 
x_7 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__2), 3, 2);
lean_closure_set(x_7, 0, x_1);
lean_closure_set(x_7, 1, x_6);
x_8 = lp_mathlib_dotProduct___redArg(x_2, x_3, x_4, x_5, x_7);
return x_8;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__3___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; 
x_7 = lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__3(x_1, x_2, x_3, x_4, x_5, x_6);
lean_dec_ref(x_4);
return x_7;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad___redArg(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9, lean_object* x_10) {
_start:
{
lean_object* x_11; lean_object* x_12; lean_object* x_13; lean_object* x_14; lean_object* x_15; lean_object* x_16; lean_object* x_17; lean_object* x_18; lean_object* x_19; lean_object* x_20; lean_object* x_21; 
x_11 = lean_ctor_get(x_1, 0);
lean_inc_ref(x_11);
lean_dec_ref(x_1);
x_12 = lp_mathlib_CommRing_toNonUnitalCommRing___redArg(x_11);
x_13 = lp_mathlib_NonUnitalNonAssocRing_toNonUnitalNonAssocSemiring___redArg(x_12);
lean_inc_ref(x_13);
x_14 = lp_mathlib_NonUnitalNonAssocSemiring_toDistrib___redArg(x_13);
x_15 = lean_ctor_get(x_14, 0);
lean_inc(x_15);
lean_dec_ref(x_14);
x_16 = lean_ctor_get(x_13, 0);
lean_inc_ref(x_16);
lean_dec_ref(x_13);
x_17 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__0), 3, 2);
lean_closure_set(x_17, 0, x_8);
lean_closure_set(x_17, 1, x_10);
x_18 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__1), 4, 3);
lean_closure_set(x_18, 0, x_4);
lean_closure_set(x_18, 1, x_6);
lean_closure_set(x_18, 2, x_9);
x_19 = lean_apply_1(x_5, x_7);
lean_inc_ref(x_16);
lean_inc(x_15);
x_20 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__3___boxed), 6, 5);
lean_closure_set(x_20, 0, x_19);
lean_closure_set(x_20, 1, x_3);
lean_closure_set(x_20, 2, x_15);
lean_closure_set(x_20, 3, x_16);
lean_closure_set(x_20, 4, x_18);
x_21 = lp_mathlib_dotProduct___redArg(x_2, x_15, x_16, x_20, x_17);
lean_dec_ref(x_16);
return x_21;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelQuad(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9, lean_object* x_10, lean_object* x_11, lean_object* x_12, lean_object* x_13, lean_object* x_14, lean_object* x_15) {
_start:
{
lean_object* x_16; 
x_16 = lp_coai_KernelAttention_AttnKernelQuad___redArg(x_2, x_7, x_8, x_9, x_10, x_11, x_12, x_13, x_14, x_15);
return x_16;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg___lam__2(lean_object* x_1, lean_object* x_2, lean_object* x_3) {
_start:
{
lean_object* x_4; 
x_4 = lp_mathlib_Matrix_transpose___redArg(x_1, x_2, x_3);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg___lam__0(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; lean_object* x_8; 
x_7 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelLin___redArg___lam__2), 3, 2);
lean_closure_set(x_7, 0, x_1);
lean_closure_set(x_7, 1, x_6);
x_8 = lp_mathlib_dotProduct___redArg(x_2, x_3, x_4, x_7, x_5);
return x_8;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg___lam__0___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; 
x_7 = lp_coai_KernelAttention_AttnKernelLin___redArg___lam__0(x_1, x_2, x_3, x_4, x_5, x_6);
lean_dec_ref(x_4);
return x_7;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin___redArg(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9, lean_object* x_10) {
_start:
{
lean_object* x_11; lean_object* x_12; lean_object* x_13; lean_object* x_14; lean_object* x_15; lean_object* x_16; lean_object* x_17; lean_object* x_18; lean_object* x_19; lean_object* x_20; lean_object* x_21; 
x_11 = lean_ctor_get(x_1, 0);
lean_inc_ref(x_11);
lean_dec_ref(x_1);
x_12 = lp_mathlib_CommRing_toNonUnitalCommRing___redArg(x_11);
x_13 = lp_mathlib_NonUnitalNonAssocRing_toNonUnitalNonAssocSemiring___redArg(x_12);
lean_inc_ref(x_13);
x_14 = lp_mathlib_NonUnitalNonAssocSemiring_toDistrib___redArg(x_13);
x_15 = lean_ctor_get(x_14, 0);
lean_inc(x_15);
lean_dec_ref(x_14);
x_16 = lean_ctor_get(x_13, 0);
lean_inc_ref(x_16);
lean_dec_ref(x_13);
x_17 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__0), 3, 2);
lean_closure_set(x_17, 0, x_8);
lean_closure_set(x_17, 1, x_10);
x_18 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelQuad___redArg___lam__1), 4, 3);
lean_closure_set(x_18, 0, x_4);
lean_closure_set(x_18, 1, x_6);
lean_closure_set(x_18, 2, x_9);
x_19 = lean_apply_1(x_5, x_7);
lean_inc_ref(x_16);
lean_inc(x_15);
x_20 = lean_alloc_closure((void*)(lp_coai_KernelAttention_AttnKernelLin___redArg___lam__0___boxed), 6, 5);
lean_closure_set(x_20, 0, x_19);
lean_closure_set(x_20, 1, x_2);
lean_closure_set(x_20, 2, x_15);
lean_closure_set(x_20, 3, x_16);
lean_closure_set(x_20, 4, x_17);
x_21 = lp_mathlib_dotProduct___redArg(x_3, x_15, x_16, x_18, x_20);
lean_dec_ref(x_16);
return x_21;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_AttnKernelLin(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9, lean_object* x_10, lean_object* x_11, lean_object* x_12, lean_object* x_13, lean_object* x_14, lean_object* x_15) {
_start:
{
lean_object* x_16; 
x_16 = lp_coai_KernelAttention_AttnKernelLin___redArg(x_2, x_7, x_8, x_9, x_10, x_11, x_12, x_13, x_14, x_15);
return x_16;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_OuterN___redArg___lam__0(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; lean_object* x_8; lean_object* x_9; 
lean_inc(x_6);
x_7 = lean_apply_2(x_1, x_6, x_2);
x_8 = lean_apply_2(x_3, x_6, x_4);
x_9 = lean_apply_2(x_5, x_7, x_8);
return x_9;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_OuterN___redArg(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6) {
_start:
{
lean_object* x_7; lean_object* x_8; lean_object* x_9; lean_object* x_10; lean_object* x_11; lean_object* x_12; lean_object* x_13; lean_object* x_14; 
x_7 = lean_ctor_get(x_1, 0);
lean_inc_ref(x_7);
lean_dec_ref(x_1);
x_8 = lp_mathlib_CommRing_toNonUnitalCommRing___redArg(x_7);
x_9 = lp_mathlib_NonUnitalNonAssocRing_toNonUnitalNonAssocSemiring___redArg(x_8);
x_10 = lean_ctor_get(x_9, 0);
lean_inc_ref(x_10);
x_11 = lp_mathlib_NonUnitalNonAssocSemiring_toDistrib___redArg(x_9);
x_12 = lean_ctor_get(x_11, 0);
lean_inc(x_12);
lean_dec_ref(x_11);
x_13 = lean_alloc_closure((void*)(lp_coai_KernelAttention_OuterN___redArg___lam__0), 6, 5);
lean_closure_set(x_13, 0, x_3);
lean_closure_set(x_13, 1, x_5);
lean_closure_set(x_13, 2, x_4);
lean_closure_set(x_13, 3, x_6);
lean_closure_set(x_13, 4, x_12);
x_14 = lp_mathlib_Finset_sum___redArg(x_10, x_2, x_13);
lean_dec_ref(x_10);
return x_14;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_OuterN(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8, lean_object* x_9, lean_object* x_10) {
_start:
{
lean_object* x_11; 
x_11 = lp_coai_KernelAttention_OuterN___redArg(x_2, x_6, x_7, x_8, x_9, x_10);
return x_11;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_ones___redArg(lean_object* x_1) {
_start:
{
lean_object* x_2; lean_object* x_3; lean_object* x_4; lean_object* x_5; lean_object* x_6; 
x_2 = lp_mathlib_Field_toDivisionRing___redArg(x_1);
x_3 = lean_ctor_get(x_2, 0);
lean_inc_ref(x_3);
lean_dec_ref(x_2);
x_4 = lp_mathlib_Ring_toAddGroupWithOne___redArg(x_3);
x_5 = lean_ctor_get(x_4, 1);
lean_inc_ref(x_5);
lean_dec_ref(x_4);
x_6 = lean_ctor_get(x_5, 2);
lean_inc(x_6);
lean_dec_ref(x_5);
return x_6;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_ones(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5) {
_start:
{
lean_object* x_6; 
x_6 = lp_coai_KernelAttention_ones___redArg(x_2);
return x_6;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_ones___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5) {
_start:
{
lean_object* x_6; 
x_6 = lp_coai_KernelAttention_ones(x_1, x_2, x_3, x_4, x_5);
lean_dec(x_5);
lean_dec(x_4);
return x_6;
}
}
static lean_object* _init_lp_coai_KernelAttention_Normalize___redArg___closed__0() {
_start:
{
lean_object* x_1; lean_object* x_2; lean_object* x_3; 
x_1 = lean_unsigned_to_nat(1u);
x_2 = lean_unsigned_to_nat(0u);
x_3 = lean_nat_mod(x_2, x_1);
return x_3;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_Normalize___redArg(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5) {
_start:
{
lean_object* x_6; lean_object* x_7; lean_object* x_8; lean_object* x_9; lean_object* x_10; lean_object* x_11; lean_object* x_12; 
x_6 = lp_mathlib_Field_toDivisionRing___redArg(x_1);
x_7 = lp_mathlib_DivisionRing_toDivInvMonoid___redArg(x_6);
x_8 = lean_ctor_get(x_7, 2);
lean_inc(x_8);
lean_dec_ref(x_7);
lean_inc(x_4);
x_9 = lean_apply_2(x_2, x_4, x_5);
x_10 = lp_coai_KernelAttention_Normalize___redArg___closed__0;
x_11 = lean_apply_2(x_3, x_4, x_10);
x_12 = lean_apply_2(x_8, x_9, x_11);
return x_12;
}
}
LEAN_EXPORT lean_object* lp_coai_KernelAttention_Normalize(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5, lean_object* x_6, lean_object* x_7, lean_object* x_8) {
_start:
{
lean_object* x_9; 
x_9 = lp_coai_KernelAttention_Normalize___redArg(x_2, x_5, x_6, x_7, x_8);
return x_9;
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Data_Matrix_Basic(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_CoAI_LinearRouting(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Data_Matrix_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
lp_coai_KernelAttention_Normalize___redArg___closed__0 = _init_lp_coai_KernelAttention_Normalize___redArg___closed__0();
lean_mark_persistent(lp_coai_KernelAttention_Normalize___redArg___closed__0);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
