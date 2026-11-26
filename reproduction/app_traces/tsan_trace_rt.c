#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * Lightweight TSan-ABI memory-access tracer.
 * Programs compiled with `clang++ -O2 -fsanitize=thread` call these hooks on
 * every memory load/store. We log the 4 KiB virtual page (addr >> 12) when
 * tracing is enabled (after cold initialization), with configurable stride/cap.
 */
static FILE *g_fp = NULL;
static uint64_t g_buf[16384];
static size_t g_buf_n = 0;
static size_t g_logged = 0;
static size_t g_seen = 0;
static size_t g_skip = 0;
static size_t g_max = 600000;
static size_t g_sample_mod = 1;
static int g_active = 1;

void tsan_trace_set_active(int active) { g_active = active; }

static inline void flush_buf(void) {
    if (g_fp && g_buf_n > 0) {
        fwrite(g_buf, sizeof(uint64_t), g_buf_n, g_fp);
        g_buf_n = 0;
    }
}

static inline void record_addr(const void *p) {
    if (!g_active || !g_fp || g_logged >= g_max) return;
    g_seen++;
    if (g_seen <= g_skip) return;
    if (g_sample_mod > 1 && (g_seen % g_sample_mod) != 0) return;
    g_buf[g_buf_n++] = ((uintptr_t)p) >> 12;
    g_logged++;
    if (g_buf_n == 16384) flush_buf();
}

void __tsan_init(void) {
    const char *out = getenv("VM_TRACE_OUT");
    if (out && *out) g_fp = fopen(out, "wb");
    const char *sk = getenv("VM_TRACE_SKIP");
    if (sk && *sk) g_skip = strtoull(sk, NULL, 10);
    const char *mx = getenv("VM_TRACE_MAX");
    if (mx && *mx) g_max = strtoull(mx, NULL, 10);
    const char *sm = getenv("VM_TRACE_STRIDE");
    if (sm && *sm) {
        g_sample_mod = strtoull(sm, NULL, 10);
        if (g_sample_mod == 0) g_sample_mod = 1;
    }
}

void __tsan_func_entry(void *pc) { (void)pc; }
void __tsan_func_exit(void) {}
void __tsan_vptr_read(void **p) { record_addr(p); }
void __tsan_vptr_update(void **p, void *v) { (void)v; record_addr(p); }
void __tsan_read_range(void *p, unsigned long sz) { (void)sz; record_addr(p); }
void __tsan_write_range(void *p, unsigned long sz) { (void)sz; record_addr(p); }
void *__tsan_memcpy(void *dst, const void *src, size_t n) {
    record_addr(src);
    record_addr(dst);
    return memcpy(dst, src, n);
}
void *__tsan_memmove(void *dst, const void *src, size_t n) {
    record_addr(src);
    record_addr(dst);
    return memmove(dst, src, n);
}
void *__tsan_memset(void *dst, int c, size_t n) {
    record_addr(dst);
    return memset(dst, c, n);
}

#define DEF_TSAN(N) \
  void __tsan_read##N(void *p) { record_addr(p); } \
  void __tsan_write##N(void *p) { record_addr(p); } \
  void __tsan_unaligned_read##N(void *p) { record_addr(p); } \
  void __tsan_unaligned_write##N(void *p) { record_addr(p); }

DEF_TSAN(1)
DEF_TSAN(2)
DEF_TSAN(4)
DEF_TSAN(8)
DEF_TSAN(16)

__attribute__((destructor)) static void tsan_fini(void) {
    flush_buf();
    if (g_fp) fclose(g_fp);
}
