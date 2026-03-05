// Lean compiler output
// Module: Main
// Imports: public import Init public import CoAI.Substrate public import CoAI.Composition public import CoAI.Control public import CoAI.Economics public import CoAI.Example public import CoAI.LinearRouting public import CoAI.ExpectedRouting
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
static const lean_string_object lp_coai_main___closed__0_value = {.m_header = {.m_rc = 0, .m_cs_sz = 0, .m_other = 0, .m_tag = 249}, .m_size = 23, .m_capacity = 23, .m_length = 22, .m_data = "CoAI Substrate Loaded."};
static const lean_object* lp_coai_main___closed__0 = (const lean_object*)&lp_coai_main___closed__0_value;
lean_object* l_IO_println___at___00__private_Lean_Shell_0__Lean_ShellOptions_process_spec__3(lean_object*);
LEAN_EXPORT lean_object* _lean_main();
LEAN_EXPORT lean_object* lp_coai_main___boxed(lean_object*);
LEAN_EXPORT lean_object* _lean_main() {
_start:
{
lean_object* x_2; lean_object* x_3; 
x_2 = ((lean_object*)(lp_coai_main___closed__0));
x_3 = l_IO_println___at___00__private_Lean_Shell_0__Lean_ShellOptions_process_spec__3(x_2);
return x_3;
}
}
LEAN_EXPORT lean_object* lp_coai_main___boxed(lean_object* x_1) {
_start:
{
lean_object* x_2; 
x_2 = _lean_main();
return x_2;
}
}
lean_object* initialize_Init(uint8_t builtin);
lean_object* initialize_coai_CoAI_Substrate(uint8_t builtin);
lean_object* initialize_coai_CoAI_Composition(uint8_t builtin);
lean_object* initialize_coai_CoAI_Control(uint8_t builtin);
lean_object* initialize_coai_CoAI_Economics(uint8_t builtin);
lean_object* initialize_coai_CoAI_Example(uint8_t builtin);
lean_object* initialize_coai_CoAI_LinearRouting(uint8_t builtin);
lean_object* initialize_coai_CoAI_ExpectedRouting(uint8_t builtin);
static bool _G_initialized = false;
LEAN_EXPORT lean_object* initialize_coai_Main(uint8_t builtin) {
lean_object * res;
if (_G_initialized) return lean_io_result_mk_ok(lean_box(0));
_G_initialized = true;
res = initialize_Init(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_Substrate(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_Composition(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_Control(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_Economics(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_Example(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_LinearRouting(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
res = initialize_coai_CoAI_ExpectedRouting(builtin);
if (lean_io_result_is_error(res)) return res;
lean_dec_ref(res);
return lean_io_result_mk_ok(lean_box(0));
}
char ** lean_setup_args(int argc, char ** argv);
void lean_initialize();

  #if defined(WIN32) || defined(_WIN32)
  #include <windows.h>
  #endif

  int main(int argc, char ** argv) {
  #if defined(WIN32) || defined(_WIN32)
  SetErrorMode(SEM_FAILCRITICALERRORS);
  SetConsoleOutputCP(CP_UTF8);
  #endif
  lean_object* in; lean_object* res;
argv = lean_setup_args(argc, argv);
lean_initialize();
lean_set_panic_messages(false);
res = initialize_coai_Main(1 /* builtin */);
lean_set_panic_messages(true);
lean_io_mark_end_initialization();
if (lean_io_result_is_ok(res)) {
lean_dec_ref(res);
lean_init_task_manager();
res = _lean_main();
}
lean_finalize_task_manager();
if (lean_io_result_is_ok(res)) {
  int ret = 0;
  lean_dec_ref(res);
  return ret;
} else {
  lean_io_result_show_error(res);
  lean_dec_ref(res);
  return 1;
}
}
#ifdef __cplusplus
}
#endif
