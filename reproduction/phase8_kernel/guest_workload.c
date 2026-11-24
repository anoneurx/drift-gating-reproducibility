#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>

#define NREFS       1000000ULL
#define PHASE_REFS  250000ULL
#define WARM        100000ULL
#define PHASE_PAGES (128ULL * 1024 * 1024 / 4096)
#define ARENA_PAGES (512ULL * 1024 * 1024 / 4096)
#define MEM_LIMIT   "268435456"

static void wr(const char *p, const char *v) {
  int fd = open(p, O_WRONLY);
  if (fd < 0) { perror(p); return; }
  ssize_t n = write(fd, v, strlen(v));
  if (n < 0) perror(p);
  close(fd);
}
static double ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (double)t.tv_sec * 1e9 + t.tv_nsec; }
static uint64_t xs(uint64_t *s) { uint64_t x = *s; x ^= x << 13; x ^= x >> 7; x ^= x << 17; return *s = x; }

int main(void) {
  char buf[128];
  wr("/sys/fs/cgroup/da/memory.max", MEM_LIMIT);
  wr("/sys/fs/cgroup/da/memory.swap.max", "0\n");
  snprintf(buf, sizeof(buf), "%d\n", (int)getpid());
  wr("/sys/fs/cgroup/da/cgroup.procs", buf);

  void *base = mmap(NULL, (size_t)ARENA_PAGES * 4096, PROT_READ | PROT_WRITE,
                    MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
  if (base == MAP_FAILED) { perror("mmap"); return 1; }

  struct rusage r0, r1;
  getrusage(RUSAGE_SELF, &r0);
  double t0 = ns(), acc = 0.0;
  uint64_t *perm = malloc((size_t)PHASE_PAGES * sizeof(uint64_t));
  if (!perm) return 1;

  static const uint64_t phase_seeds[4] = {101ULL, 202ULL, 303ULL, 404ULL};
  for (uint64_t ph = 0; ph < 4; ph++) {
    uint64_t seed = phase_seeds[ph];
    for (uint64_t i = 0; i < PHASE_PAGES; i++) perm[i] = i;
    for (uint64_t i = PHASE_PAGES - 1; i > 0; i--) {
      uint64_t j = xs(&seed) % (i + 1);
      uint64_t tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
    }
    unsigned char *phase_base = (unsigned char *)base + (size_t)(ph * PHASE_PAGES * 4096);
    for (uint64_t i = 0; i < PHASE_REFS; i++) {
      volatile unsigned char *p = phase_base + (size_t)(perm[i % PHASE_PAGES] * 4096);
      double a = 0;
      if (ph * PHASE_REFS + i >= WARM) a = ns();
      *p ^= 1;
      if (a) acc += ns() - a;
    }
  }
  getrusage(RUSAGE_SELF, &r1);
  double elapsed = ns() - t0;
  printf("workload,refs=%llu,warm=%llu,elapsed_ns=%.1f,access_ns_sum=%.1f,minflt=%ld,majflt=%ld\n",
         (unsigned long long)NREFS, (unsigned long long)WARM, elapsed, acc,
         r1.ru_minflt - r0.ru_minflt, r1.ru_majflt - r0.ru_majflt);
  fflush(stdout);
  free(perm);
  return 0;
}
