#!/bin/sh
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
RESULTS="$HERE/results"
KERNEL="$HERE/bzImage"
INITRD="$HERE/initramfs.cpio.gz"
rm -rf "$RESULTS"
mkdir -p "$RESULTS"
qemu-system-x86_64 --version > "$RESULTS/qemu_version.txt"

boot() {
  cond=$1
  rep=$2
  out="$RESULTS/$cond/$rep"
  mkdir -p "$out"
  printf '%s\n' "$cond" > "$RESULTS/condition"
  printf '%s\n' "$rep" > "$RESULTS/repetition"
  timeout 300 qemu-system-x86_64 -enable-kvm -m 2048 -smp 2 -no-reboot \
    -display none -serial "file:$out/console.log" \
    -kernel "$KERNEL" -initrd "$INITRD" \
    -append "console=ttyS0 panic=-1" \
    -fsdev local,id=res,path="$RESULTS",security_model=none \
    -device virtio-9p-pci,fsdev=res,mount_tag=results
  if [ ! -f "$out/done" ]; then
    echo "FAILED: $cond rep $rep did not complete" >&2
    return 1
  fi
}

echo "discovery boot"
boot discover 1
python3 "$HERE/make_ftrace_filter.py"

for cond in fixed_lru fixed_mglru coupled; do
  for rep in 1 2 3; do
    echo "running $cond rep $rep"
    boot "$cond" "$rep"
  done
done

python3 "$HERE/parse_ftrace.py"
python3 "$HERE/summarize_kernel.py"
echo "kernel phase complete"
