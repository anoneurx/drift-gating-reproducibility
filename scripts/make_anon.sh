#!/usr/bin/env bash
# =============================================================================
# scripts/make_anon.sh
# Create an anonymised copy of the artifact for blind review.
# Output: artifact_anonymous/   (safe to upload as supplementary material)
# =============================================================================
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="$SRC/artifact_anonymous"

echo "Creating anonymised copy in $DST ..."
rm -rf "$DST"
mkdir -p "$DST"

# Directories to copy (no large binary traces)
DIRS=(src tracer configs scripts traces results figures tests supplement)
for d in "${DIRS[@]}"; do
    [[ -d "$SRC/$d" ]] && cp -r "$SRC/$d" "$DST/$d"
done

# Top-level files
for f in Makefile LICENSE requirements.txt environment.md; do
    [[ -f "$SRC/$f" ]] && cp "$SRC/$f" "$DST/$f"
done

# CITATION.cff — scrub author names
sed 's/name:.*/name: "Anonymous Authors"/' "$SRC/CITATION.cff" > "$DST/CITATION.cff"

# Strip email addresses from all copied files
find "$DST" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.md" -o -name "*.txt" -o -name "*.yaml" -o -name "*.cff" \) | while read -r f; do
    sed -i 's/[a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]*\.[a-zA-Z]\{2,\}/anonymous@review.blind/g' "$f"
done

# Strip absolute home paths
find "$DST" -type f \( -name "*.py" -o -name "*.sh" -o -name "*.md" \) | while read -r f; do
    sed -i 's|/home/[^/]*/[^ "'"'"']*|/workspace/artifact|g' "$f"
done

# Remove large binaries excluded from anon copy
find "$DST" -name "*.bin" -size +5M -delete
find "$DST" -name "bzImage" -delete

# Write anonymised README
cp "$SRC/README.md" "$DST/README.md"
sed -i 's/itskashie@anoneurx\.com/anonymous@review.blind/g' "$DST/README.md"
sed -i 's/anoneurx//g' "$DST/README.md"

echo "Done.  Anonymised artifact is in: $DST"
echo "Verify before upload:"
echo "  grep -rn 'kashie\|anoneurx\|@' $DST --include='*.md' --include='*.py' --include='*.yaml'"
