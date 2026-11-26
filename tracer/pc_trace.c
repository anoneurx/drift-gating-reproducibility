#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

/*
 * LD_PRELOAD page-cache tracer for unmodified Linux binaries.
 * Logs 4 KiB file-page keys (64-bit dev/ino/page_index) from read/write/
 * pread/pwrite/fread/fwrite/mmap syscalls on regular files.
 */
static pthread_mutex_t g_lock = PTHREAD_MUTEX_INITIALIZER;
static int g_out_fd = -1;
static int g_inited = 0;
static uint64_t g_fd_dev[4096], g_fd_ino[4096];
static int64_t g_fd_off[4096];
static int g_fd_track[4096];

static ssize_t (*real_read)(int, void *, size_t);
static ssize_t (*real_pread)(int, void *, size_t, off_t);
static ssize_t (*real_pread64)(int, void *, size_t, off64_t);
static ssize_t (*real_write)(int, const void *, size_t);
static ssize_t (*real_pwrite)(int, const void *, size_t, off_t);
static ssize_t (*real_pwrite64)(int, const void *, size_t, off64_t);
static off_t (*real_lseek)(int, off_t, int);
static off64_t (*real_lseek64)(int, off64_t, int);
static int (*real_open)(const char *, int, ...);
static int (*real_open64)(const char *, int, ...);
static int (*real_openat)(int, const char *, int, ...);
static int (*real_openat64)(int, const char *, int, ...);
static int (*real_close)(int);
static FILE *(*real_fopen)(const char *, const char *);
static FILE *(*real_fopen64)(const char *, const char *);
static size_t (*real_fread)(void *, size_t, size_t, FILE *);
static size_t (*real_fwrite)(const void *, size_t, size_t, FILE *);
static void *(*real_mmap)(void *, size_t, int, int, int, off_t);
static void *(*real_mmap64)(void *, size_t, int, int, int, off64_t);

static uint64_t g_buf[8192];
static size_t g_buf_n = 0;
static size_t g_total_written = 0;
static size_t g_max_refs = 1000000;

static void flush_buf(void) {
    if (g_out_fd >= 0 && g_buf_n > 0) {
        ssize_t w = real_write(g_out_fd, g_buf, g_buf_n * sizeof(uint64_t));
        (void)w;
        g_buf_n = 0;
    }
}

__attribute__((constructor))
static void init_syms(void) {
    if (g_inited) return;
    g_inited = 1;
    real_read = dlsym(RTLD_NEXT, "read");
    real_pread = dlsym(RTLD_NEXT, "pread");
    real_pread64 = dlsym(RTLD_NEXT, "pread64");
    real_write = dlsym(RTLD_NEXT, "write");
    real_pwrite = dlsym(RTLD_NEXT, "pwrite");
    real_pwrite64 = dlsym(RTLD_NEXT, "pwrite64");
    real_lseek = dlsym(RTLD_NEXT, "lseek");
    real_lseek64 = dlsym(RTLD_NEXT, "lseek64");
    real_open = dlsym(RTLD_NEXT, "open");
    real_open64 = dlsym(RTLD_NEXT, "open64");
    real_openat = dlsym(RTLD_NEXT, "openat");
    real_openat64 = dlsym(RTLD_NEXT, "openat64");
    real_close = dlsym(RTLD_NEXT, "close");
    real_fopen = dlsym(RTLD_NEXT, "fopen");
    real_fopen64 = dlsym(RTLD_NEXT, "fopen64");
    real_fread = dlsym(RTLD_NEXT, "fread");
    real_fwrite = dlsym(RTLD_NEXT, "fwrite");
    real_mmap = dlsym(RTLD_NEXT, "mmap");
    real_mmap64 = dlsym(RTLD_NEXT, "mmap64");
    const char *p = getenv("PC_TRACE_OUT");
    if (p && *p) g_out_fd = real_open(p, O_WRONLY | O_CREAT | O_APPEND, 0644);
    const char *mr = getenv("PC_TRACE_MAX");
    if (mr && *mr) g_max_refs = strtoull(mr, NULL, 10);
}

static void record_fd(int fd) {
    if (fd < 3 || fd >= 4096 || fd == g_out_fd) return;
    struct stat st;
    if (fstat(fd, &st) == 0 && S_ISREG(st.st_mode)) {
        g_fd_dev[fd] = (uint64_t)st.st_dev;
        g_fd_ino[fd] = (uint64_t)st.st_ino;
        g_fd_off[fd] = 0;
        g_fd_track[fd] = 1;
    } else {
        g_fd_track[fd] = 0;
    }
}

static void emit_pages(int fd, off64_t off, size_t len) {
    if (g_out_fd < 0 || fd < 3 || fd >= 4096 || !g_fd_track[fd] || len == 0) return;
    uint64_t p0 = (uint64_t)off >> 12;
    uint64_t p1 = (uint64_t)(off + len - 1) >> 12;
    pthread_mutex_lock(&g_lock);
    for (uint64_t pg = p0; pg <= p1 && g_total_written < g_max_refs; pg++) {
        uint64_t key = (g_fd_ino[fd] * 1315423911ULL) ^ pg ^ (g_fd_dev[fd] << 48);
        g_buf[g_buf_n++] = key;
        g_total_written++;
        if (g_buf_n == 8192) flush_buf();
    }
    pthread_mutex_unlock(&g_lock);
}

int open(const char *path, int flags, ...) {
    init_syms();
    mode_t m = 0;
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); m = va_arg(ap, mode_t); va_end(ap); }
    int fd = (flags & O_CREAT) ? real_open(path, flags, m) : real_open(path, flags);
    if (fd >= 0) record_fd(fd);
    return fd;
}
int open64(const char *path, int flags, ...) {
    init_syms();
    mode_t m = 0;
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); m = va_arg(ap, mode_t); va_end(ap); }
    int fd = (flags & O_CREAT) ? real_open64(path, flags, m) : real_open64(path, flags);
    if (fd >= 0) record_fd(fd);
    return fd;
}
int openat(int dfd, const char *path, int flags, ...) {
    init_syms();
    mode_t m = 0;
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); m = va_arg(ap, mode_t); va_end(ap); }
    int fd = (flags & O_CREAT) ? real_openat(dfd, path, flags, m) : real_openat(dfd, path, flags);
    if (fd >= 0) record_fd(fd);
    return fd;
}
int openat64(int dfd, const char *path, int flags, ...) {
    init_syms();
    mode_t m = 0;
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); m = va_arg(ap, mode_t); va_end(ap); }
    int fd = (flags & O_CREAT) ? real_openat64(dfd, path, flags, m) : real_openat64(dfd, path, flags);
    if (fd >= 0) record_fd(fd);
    return fd;
}
FILE *fopen(const char *path, const char *mode) {
    init_syms();
    FILE *f = real_fopen(path, mode);
    if (f) record_fd(fileno(f));
    return f;
}
FILE *fopen64(const char *path, const char *mode) {
    init_syms();
    FILE *f = real_fopen64(path, mode);
    if (f) record_fd(fileno(f));
    return f;
}
int close(int fd) {
    init_syms();
    if (fd >= 0 && fd < 4096) g_fd_track[fd] = 0;
    return real_close(fd);
}
ssize_t read(int fd, void *b, size_t n) {
    init_syms();
    off64_t off = (fd >= 3 && fd < 4096 && g_fd_track[fd]) ? g_fd_off[fd] : 0;
    ssize_t r = real_read(fd, b, n);
    if (r > 0 && fd >= 3 && fd < 4096 && g_fd_track[fd]) {
        emit_pages(fd, off, (size_t)r);
        g_fd_off[fd] = off + r;
    }
    return r;
}
ssize_t write(int fd, const void *b, size_t n) {
    init_syms();
    off64_t off = (fd >= 3 && fd < 4096 && g_fd_track[fd]) ? g_fd_off[fd] : 0;
    ssize_t r = real_write(fd, b, n);
    if (r > 0 && fd >= 3 && fd < 4096 && g_fd_track[fd]) {
        emit_pages(fd, off, (size_t)r);
        g_fd_off[fd] = off + r;
    }
    return r;
}
ssize_t pread(int fd, void *b, size_t n, off_t off) {
    init_syms();
    ssize_t r = real_pread(fd, b, n, off);
    if (r > 0) emit_pages(fd, off, (size_t)r);
    return r;
}
ssize_t pread64(int fd, void *b, size_t n, off64_t off) {
    init_syms();
    ssize_t r = real_pread64(fd, b, n, off);
    if (r > 0) emit_pages(fd, off, (size_t)r);
    return r;
}
ssize_t pwrite(int fd, const void *b, size_t n, off_t off) {
    init_syms();
    ssize_t r = real_pwrite(fd, b, n, off);
    if (r > 0) emit_pages(fd, off, (size_t)r);
    return r;
}
ssize_t pwrite64(int fd, const void *b, size_t n, off64_t off) {
    init_syms();
    ssize_t r = real_pwrite64(fd, b, n, off);
    if (r > 0) emit_pages(fd, off, (size_t)r);
    return r;
}
off_t lseek(int fd, off_t off, int w) {
    init_syms();
    off_t r = real_lseek(fd, off, w);
    if (r >= 0 && fd >= 3 && fd < 4096 && g_fd_track[fd]) g_fd_off[fd] = r;
    return r;
}
off64_t lseek64(int fd, off64_t off, int w) {
    init_syms();
    off64_t r = real_lseek64(fd, off, w);
    if (r >= 0 && fd >= 3 && fd < 4096 && g_fd_track[fd]) g_fd_off[fd] = r;
    return r;
}
size_t fread(void *ptr, size_t size, size_t nmemb, FILE *stream) {
    init_syms();
    int fd = fileno(stream);
    if (fd >= 3 && fd < 4096 && !g_fd_track[fd]) record_fd(fd);
    off64_t off = (fd >= 3 && fd < 4096 && g_fd_track[fd]) ? g_fd_off[fd] : 0;
    size_t r = real_fread(ptr, size, nmemb, stream);
    if (r > 0 && fd >= 3 && fd < 4096 && g_fd_track[fd]) {
        size_t bytes = r * size;
        emit_pages(fd, off, bytes);
        g_fd_off[fd] = off + (off64_t)bytes;
    }
    return r;
}
size_t fwrite(const void *ptr, size_t size, size_t nmemb, FILE *stream) {
    init_syms();
    int fd = fileno(stream);
    if (fd >= 3 && fd < 4096 && !g_fd_track[fd]) record_fd(fd);
    off64_t off = (fd >= 3 && fd < 4096 && g_fd_track[fd]) ? g_fd_off[fd] : 0;
    size_t r = real_fwrite(ptr, size, nmemb, stream);
    if (r > 0 && fd >= 3 && fd < 4096 && g_fd_track[fd]) {
        size_t bytes = r * size;
        emit_pages(fd, off, bytes);
        g_fd_off[fd] = off + (off64_t)bytes;
    }
    return r;
}
void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t off) {
    init_syms();
    void *res = real_mmap(addr, len, prot, flags, fd, off);
    if (res != MAP_FAILED && fd >= 3 && fd < 4096) {
        if (!g_fd_track[fd]) record_fd(fd);
        emit_pages(fd, off, len);
    }
    return res;
}
void *mmap64(void *addr, size_t len, int prot, int flags, int fd, off64_t off) {
    init_syms();
    void *res = real_mmap64(addr, len, prot, flags, fd, off);
    if (res != MAP_FAILED && fd >= 3 && fd < 4096) {
        if (!g_fd_track[fd]) record_fd(fd);
        emit_pages(fd, off, len);
    }
    return res;
}
__attribute__((destructor)) static void pc_fini(void) {
    pthread_mutex_lock(&g_lock);
    flush_buf();
    if (g_out_fd >= 0) real_close(g_out_fd);
    pthread_mutex_unlock(&g_lock);
}
