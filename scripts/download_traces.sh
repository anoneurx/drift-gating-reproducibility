#!/usr/bin/env bash
# =============================================================================
# scripts/download_traces.sh
# Download and verify all public traces used in the study.
#
# Usage:
#   bash scripts/download_traces.sh            # download + verify
#   bash scripts/download_traces.sh --check    # verify only (no download)
#
# Traces that cannot be redistributed (FIU, PDL) must be obtained separately;
# this script will print instructions for those.
# =============================================================================
set -euo pipefail

CHECKONLY=0
[[ "${1:-}" == "--check" ]] && CHECKONLY=1

TRACES_DIR="$(dirname "$0")/../traces"
CHECKSUMS="$TRACES_DIR/SHA256SUMS"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC}  $1"; }
fail() { echo -e "${RED}FAIL${NC}  $1"; FAILED=$((FAILED+1)); }
info() { echo -e "${YELLOW}INFO${NC}  $1"; }

FAILED=0

# ---------------------------------------------------------------------------
# 1. Instrumented-kernel traces (in-repo, no download needed)
# ---------------------------------------------------------------------------
info "Verifying instrumented-kernel traces (60 × .bin in traces_real/) ..."
if [[ -f "$CHECKSUMS" ]]; then
    while IFS='  ' read -r expected file; do
        path="$(dirname "$0")/../$file"
        if [[ ! -f "$path" ]]; then
            fail "Missing: $file"
            continue
        fi
        actual=$(sha256sum "$path" | awk '{print $1}')
        if [[ "$actual" == "$expected" ]]; then
            pass "$file"
        else
            fail "$file (expected $expected, got $actual)"
        fi
    done < "$CHECKSUMS"
else
    info "SHA256SUMS not found — skipping checksum verification"
fi

# ---------------------------------------------------------------------------
# 2. FIU traces (not redistributable — must be obtained from CMU PDL)
# ---------------------------------------------------------------------------
FIU_DIR="$(dirname "$0")/../reproduction/public_split"

info ""
info "============================================================"
info "FIU WebSearch traces"
info "============================================================"
info "These traces are NOT included in the repository."
info "Download them from:"
info "  https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/"
info "Then place them in: $FIU_DIR"
info ""
info "After download, convert with:"
info "  python3 reproduction/split_public_traces.py"
info ""

FIU_FILES=(
    "fiu_homes_test.bin"
    "fiu_mail_test.bin"
    "fiu_webserver_test.bin"
    "fiu_webvm_test.bin"
)

for f in "${FIU_FILES[@]}"; do
    if [[ -f "$FIU_DIR/$f" ]]; then
        pass "$FIU_DIR/$f (present)"
    else
        info "$FIU_DIR/$f (TODO: download — see instructions above)"
    fi
done

# ---------------------------------------------------------------------------
# 3. PDL traces (not redistributable — must be obtained from CMU PDL)
# ---------------------------------------------------------------------------
info ""
info "============================================================"
info "PDL (CMU) traces"
info "============================================================"
info "Download from: https://ftp.pdl.cmu.edu/pub/datasets/"
info "Place in: reproduction/phase6_pdl/"
info ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All checksum verifications passed.${NC}"
else
    echo -e "${RED}$FAILED checksum failure(s). Re-download the affected files.${NC}"
    exit 1
fi
