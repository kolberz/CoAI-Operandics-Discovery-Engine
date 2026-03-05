// Lean compiler output
// Module: CoAI.Substrate
// Imports: public import Init public import Mathlib.Data.Real.Basic public import Mathlib.Data.Countable.Defs public import Mathlib.Probability.ProbabilityMassFunction.Basic public import Mathlib.Probability.ProbabilityMassFunction.Monad public import Mathlib.Tactic.Linarith
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
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorIdx(uint8_t);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorIdx___boxed(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_toCtorIdx(uint8_t);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_toCtorIdx___boxed(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim___redArg(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim___redArg___boxed(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim(lean_object*, lean_object*, uint8_t, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim___boxed(lean_object*, lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim___redArg(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim___redArg___boxed(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim(lean_object*, uint8_t, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim___boxed(lean_object*, lean_object*, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim___redArg(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim___redArg___boxed(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim(lean_object*, uint8_t, lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim___boxed(lean_object*, lean_object*, lean_object*, lean_object*);
uint8_t lean_nat_dec_le(lean_object*, lean_object*);
LEAN_EXPORT uint8_t lp_coai_CoAI_Substrate_Bit_ofNat(lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ofNat___boxed(lean_object*);
uint8_t lean_nat_dec_eq(lean_object*, lean_object*);
LEAN_EXPORT uint8_t lp_coai_CoAI_Substrate_instDecidableEqBit(uint8_t, uint8_t);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_instDecidableEqBit___boxed(lean_object*, lean_object*);
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorIdx(uint8_t x_1) {
_start:
{
if (x_1 == 0)
{
lean_object* x_2; 
x_2 = lean_unsigned_to_nat(0u);
return x_2;
}
else
{
lean_object* x_3; 
x_3 = lean_unsigned_to_nat(1u);
return x_3;
}
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorIdx___boxed(lean_object* x_1) {
_start:
{
uint8_t x_2; lean_object* x_3; 
x_2 = lean_unbox(x_1);
x_3 = lp_coai_CoAI_Substrate_Bit_ctorIdx(x_2);
return x_3;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_toCtorIdx(uint8_t x_1) {
_start:
{
lean_object* x_2; 
x_2 = lp_coai_CoAI_Substrate_Bit_ctorIdx(x_1);
return x_2;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_toCtorIdx___boxed(lean_object* x_1) {
_start:
{
uint8_t x_2; lean_object* x_3; 
x_2 = lean_unbox(x_1);
x_3 = lp_coai_CoAI_Substrate_Bit_toCtorIdx(x_2);
return x_3;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim___redArg(lean_object* x_1) {
_start:
{
lean_inc(x_1);
return x_1;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim___redArg___boxed(lean_object* x_1) {
_start:
{
lean_object* x_2; 
x_2 = lp_coai_CoAI_Substrate_Bit_ctorElim___redArg(x_1);
lean_dec(x_1);
return x_2;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim(lean_object* x_1, lean_object* x_2, uint8_t x_3, lean_object* x_4, lean_object* x_5) {
_start:
{
lean_inc(x_5);
return x_5;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ctorElim___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4, lean_object* x_5) {
_start:
{
uint8_t x_6; lean_object* x_7; 
x_6 = lean_unbox(x_3);
x_7 = lp_coai_CoAI_Substrate_Bit_ctorElim(x_1, x_2, x_6, x_4, x_5);
lean_dec(x_5);
lean_dec(x_2);
return x_7;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim___redArg(lean_object* x_1) {
_start:
{
lean_inc(x_1);
return x_1;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim___redArg___boxed(lean_object* x_1) {
_start:
{
lean_object* x_2; 
x_2 = lp_coai_CoAI_Substrate_Bit_zero_elim___redArg(x_1);
lean_dec(x_1);
return x_2;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim(lean_object* x_1, uint8_t x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
lean_inc(x_4);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_zero_elim___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
uint8_t x_5; lean_object* x_6; 
x_5 = lean_unbox(x_2);
x_6 = lp_coai_CoAI_Substrate_Bit_zero_elim(x_1, x_5, x_3, x_4);
lean_dec(x_4);
return x_6;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim___redArg(lean_object* x_1) {
_start:
{
lean_inc(x_1);
return x_1;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim___redArg___boxed(lean_object* x_1) {
_start:
{
lean_object* x_2; 
x_2 = lp_coai_CoAI_Substrate_Bit_one_elim___redArg(x_1);
lean_dec(x_1);
return x_2;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim(lean_object* x_1, uint8_t x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
lean_inc(x_4);
return x_4;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_one_elim___boxed(lean_object* x_1, lean_object* x_2, lean_object* x_3, lean_object* x_4) {
_start:
{
uint8_t x_5; lean_object* x_6; 
x_5 = lean_unbox(x_2);
x_6 = lp_coai_CoAI_Substrate_Bit_one_elim(x_1, x_5, x_3, x_4);
lean_dec(x_4);
return x_6;
}
}
LEAN_EXPORT uint8_t lp_coai_CoAI_Substrate_Bit_ofNat(lean_object* x_1) {
_start:
{
lean_object* x_2; uint8_t x_3; 
x_2 = lean_unsigned_to_nat(0u);
x_3 = lean_nat_dec_le(x_1, x_2);
if (x_3 == 0)
{
uint8_t x_4; 
x_4 = 1;
return x_4;
}
else
{
uint8_t x_5; 
x_5 = 0;
return x_5;
}
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_Bit_ofNat___boxed(lean_object* x_1) {
_start:
{
uint8_t x_2; lean_object* x_3; 
x_2 = lp_coai_CoAI_Substrate_Bit_ofNat(x_1);
lean_dec(x_1);
x_3 = lean_box(x_2);
return x_3;
}
}
LEAN_EXPORT uint8_t lp_coai_CoAI_Substrate_instDecidableEqBit(uint8_t x_1, uint8_t x_2) {
_start:
{
lean_object* x_3; lean_object* x_4; uint8_t x_5; 
x_3 = lp_coai_CoAI_Substrate_Bit_ctorIdx(x_1);
x_4 = lp_coai_CoAI_Substrate_Bit_ctorIdx(x_2);
x_5 = lean_nat_dec_eq(x_3, x_4);
lean_dec(x_4);
lean_dec(x_3);
return x_5;
}
}
LEAN_EXPORT lean_object* lp_coai_CoAI_Substrate_instDecidableEqBit___boxed(lean_object* x_1, lean_object* x_2) {
_start:
{
uint8_t x_3; uint8_t x_4; uint8_t x_5; lean_object* x_6; 
x_3 = lean_unbox(x_1);
x_4 = lean_unbox(x_2);
x_5 = lp_coai_CoAI_Substrate_instDecidableEqBit(x_3, x_4);
x_6 = lean_box(x_5);
return x_6;
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Data_Real_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Data_Countable_Defs(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Basic(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Monad(uint8_t builtin);
lean_object* initialize_mathlib_Mathlib_Tactic_Linarith(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_CoAI_Substrate(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Data_Real_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Data_Countable_Defs(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Basic(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Probability_ProbabilityMassFunction_Monad(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_mathlib_Mathlib_Tactic_Linarith(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
#ifdef __cplusplus
}
#endif
