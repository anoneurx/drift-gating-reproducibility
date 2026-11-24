#!/bin/sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
KVER=6.6.1
URL=https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-$KVER.tar.xz
WORK=/home/kashie/opencode_kernel_build
PATH="$WORK/bison-install/bin:$PATH"
ELF="$WORK/elfutils-install"
CPATH="$ELF/include:${CPATH:-}"
LIBRARY_PATH="$ELF/lib:${LIBRARY_PATH:-}"
LD_LIBRARY_PATH="$ELF/lib:${LD_LIBRARY_PATH:-}"
KCC='gcc-15 -std=gnu11'
export PATH CPATH LIBRARY_PATH LD_LIBRARY_PATH
mkdir -p "$WORK"
cd "$WORK"
if [ ! -f linux-$KVER.tar.xz ]; then
  curl -fL --retry 3 -o linux-$KVER.tar.xz "$URL"
fi
sha256sum linux-$KVER.tar.xz > "$HERE/kernel_tarball.sha256"
if [ ! -d linux-$KVER ]; then tar -xf linux-$KVER.tar.xz; fi
cd linux-$KVER
make "CC=$KCC" "HOSTCC=$KCC" clean >/dev/null 2>&1 || true
make "CC=$KCC" "HOSTCC=$KCC" defconfig
for opt in LRU_GEN LRU_GEN_ENABLED MEMCG CGROUP_MEMORY FTRACE FUNCTION_TRACER FUNCTION_GRAPH_TRACER \
           KPROBES KPROBE_EVENTS TRACING DEBUG_FS PROC_FS SYSFS TMPFS BLK_DEV_INITRD RD_GZIP \
           DEVTMPFS DEVTMPFS_MOUNT NET_9P NET_9P_VIRTIO 9P_FS VIRTIO_PCI; do
  scripts/config --enable "$opt" || true
done
make "CC=$KCC" "HOSTCC=$KCC" olddefconfig
make "CC=$KCC" "HOSTCC=$KCC" "-j$(nproc)" bzImage
cp arch/x86/boot/bzImage "$HERE/bzImage"
cp .config "$HERE/kernel.config"

ROOT="$HERE/initramfs-root"
rm -rf "$ROOT"
mkdir -p "$ROOT/bin" "$ROOT/sbin" "$ROOT/dev" "$ROOT/proc" "$ROOT/sys" "$ROOT/mnt/results" "$ROOT/sys/fs/cgroup" \
         "$ROOT/lib64" "$ROOT/lib/x86_64-linux-gnu"
cp /usr/bin/busybox "$ROOT/bin/busybox"
cp -L /lib64/ld-linux-x86-64.so.2 "$ROOT/lib64/ld-linux-x86-64.so.2"
cp -L /lib/x86_64-linux-gnu/libc.so.6 "$ROOT/lib/x86_64-linux-gnu/libc.so.6"
cp -L /lib/x86_64-linux-gnu/libresolv.so.2 "$ROOT/lib/x86_64-linux-gnu/libresolv.so.2"
for a in sh ash mount mkdir cat echo sleep sync poweroff awk head wc rm touch cp uname; do ln -sf busybox "$ROOT/bin/$a"; done
gcc -O2 -static -o "$ROOT/guest_workload" "$HERE/guest_workload.c"
gcc -O2 -static -o "$ROOT/guest_da_ctl" "$HERE/guest_da_ctl.c" -lm
cp "$HERE/init" "$ROOT/init"
chmod +x "$ROOT/init" "$ROOT/guest_workload" "$ROOT/guest_da_ctl"
(cd "$ROOT" && find . | cpio -o -H newc | gzip -9 > "$HERE/initramfs.cpio.gz")
printf '%s\n' "$KCC" > "$HERE/compiler_version.txt"
gcc --version | head -1 > "$HERE/guest_compiler_version.txt"
bison --version | head -1 > "$HERE/bison_version.txt"
{
  printf 'kernel,%s\n' "$KVER"
  printf 'url,%s\n' "$URL"
  printf 'build_root,%s\n' "$WORK"
  printf 'build_utc,%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'kernel_compiler,%s\n' "$KCC"
  printf 'guest_compiler,%s\n' "$(gcc --version | head -1)"
  printf 'bison,%s\n' "$(bison --version | head -1)"
  printf 'libelf_install,%s\n' "$ELF"
  printf 'libelf_source,elfutils-0.191\n'
  printf 'controller_interval_ms,10\n'
  printf 'controller_h,5\n'
  printf 'controller_delta,0.5\n'
  printf 'controller_edelay,10\n'
} > "$HERE/manifest.csv"
echo "guest kernel build complete: $HERE/bzImage"
