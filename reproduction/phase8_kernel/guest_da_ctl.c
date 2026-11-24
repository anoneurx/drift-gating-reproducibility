#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <math.h>

#define INTERVAL_MS 10
#define H 5.0
#define DELTA 0.5
#define EDELAY 10
#define BASE_N 8

static long vmstat_key(const char *key) {
  FILE *f = fopen("/proc/vmstat", "r");
  char k[128]; long v = 0;
  if (!f) return 0;
  while (fscanf(f, "%127s %ld", k, &v) == 2) {
    if (!strcmp(k, key)) { fclose(f); return v; }
  }
  fclose(f); return 0;
}
static long enabled_now(void) {
  FILE *f = fopen("/sys/kernel/mm/lru_gen/enabled", "r");
  long v = 0;
  if (!f) return -1;
  fscanf(f, "%i", &v);  /* base-0: sysfs reports 0x0007, not decimal 7 */
  fclose(f); return v;
}
static void wr(const char *p, const char *v) {
  int fd = open(p, O_WRONLY);
  if (fd < 0) return;
  ssize_t n = write(fd, v, strlen(v));
  (void)n; close(fd);
}
static double ns(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return (double)t.tv_sec * 1e9 + t.tv_nsec; }

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "usage: guest_da_ctl PREFIX\n"); return 1; }
  char spath[512], tpath[512], stop[512];
  snprintf(spath, sizeof(spath), "%s_samples.csv", argv[1]);
  snprintf(tpath, sizeof(tpath), "%s_toggles.csv", argv[1]);
  snprintf(stop, sizeof(stop), "%s_stop", argv[1]);
  FILE *sf = fopen(spath, "w"), *tf = fopen(tpath, "w");
  if (!sf || !tf) return 1;
  fprintf(sf, "t_ns,refault_delta,pgfault_delta,signal,z,sp,sn,enabled\n");
  fprintf(tf, "t_ns,old_enabled,new_enabled,sp\n");

  long prev_ref = vmstat_key("workingset_refault_anon");
  long prev_fault = vmstat_key("pgfault");
  double base[BASE_N], bmean = 0, bsd = 0;
  int nbase = 0, armed = 0, cooldown = 0;
  double sp = 0, sn = 0;
  struct timespec ts = {0, INTERVAL_MS * 1000000L};

  while (access(stop, F_OK) != 0) {
    nanosleep(&ts, NULL);
    long ref = vmstat_key("workingset_refault_anon");
    long fault = vmstat_key("pgfault");
    long dr = ref - prev_ref, df = fault - prev_fault;
    prev_ref = ref; prev_fault = fault;
    double sig = (double)dr / (double)(df > 1 ? df : 1);
    if (nbase < BASE_N) {
      base[nbase++] = sig;
      if (nbase == BASE_N) {
        for (int i = 0; i < BASE_N; i++) bmean += base[i] / BASE_N;
        for (int i = 0; i < BASE_N; i++) bsd += (base[i] - bmean) * (base[i] - bmean) / (BASE_N - 1);
        bsd = sqrt(bsd); armed = 1;
      }
    }
    double z = 0;
    if (armed) z = (sig - bmean) / (bsd > 1e-9 ? bsd : 1e-9);
    if (armed && cooldown == 0) {
      sp = fmax(0.0, sp + z - DELTA);
      sn = fmax(0.0, sn - z - DELTA);
      if (sp > H || sn > H) cooldown = EDELAY;
    } else if (cooldown > 0) {
      if (--cooldown == 0) {
        long old = enabled_now();
        long newv = (old == 7) ? 0 : 7;
        wr("/sys/kernel/mm/lru_gen/enabled", newv == 7 ? "0x0007" : "0x0000");
        fprintf(tf, "%.0f,%ld,%ld,%.6f\n", ns(), old, newv, sp);
        fflush(tf);
        sp = sn = 0;
      }
    }
    fprintf(sf, "%.0f,%ld,%ld,%.9f,%.9f,%.9f,%.9f,%ld\n", ns(), dr, df, sig, z, sp, sn, enabled_now());
  }
  fflush(sf); fflush(tf); fclose(sf); fclose(tf);
  return 0;
}
