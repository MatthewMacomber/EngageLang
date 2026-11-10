#ifndef ENGAGE_H
#define ENGAGE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct EngageVMHandle EngageVMHandle;

typedef double (*EngageHostNumFn)(double arg, void* userdata);

/* Lifecycle */
EngageVMHandle* engage_vm_new(void);
void engage_vm_free(EngageVMHandle* vm);

/* Script execution (returns 0 on success, non-zero on error) */
int32_t engage_eval(EngageVMHandle* vm, const char* source_ptr, size_t source_len);

/* Global variable interop */
int32_t engage_set_global_num(EngageVMHandle* vm, const char* name_ptr, size_t name_len, double value);
double engage_get_global_num(EngageVMHandle* vm, const char* name_ptr, size_t name_len);
int32_t engage_set_global_str(EngageVMHandle* vm, const char* name_ptr, size_t name_len, const char* val_ptr, size_t val_len);

/* Host function registration and calling Engage hooks (e.g. game loop on_step) */
int32_t engage_register_num_fn(EngageVMHandle* vm, const char* name_ptr, size_t name_len, EngageHostNumFn callback, void* userdata);
double engage_call_num1(EngageVMHandle* vm, const char* fn_ptr, size_t fn_len, double arg0);
double engage_call_num0(EngageVMHandle* vm, const char* fn_ptr, size_t fn_len);

#ifdef __cplusplus
}
#endif

#endif /* ENGAGE_H */
