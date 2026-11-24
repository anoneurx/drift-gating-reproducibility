#!/usr/bin/env python3
"""Read-only final hygiene report for the two paper trees.

This script creates no data. It verifies the frozen main-study artifacts,
runs the numeric checker, and reports page counts, undefined references,
overfull hboxes, and placeholder tokens in both compiled manuscripts.
"""
import hashlib
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TREES = [ROOT / "drift_gating_latex_source", ROOT / "latex"]
FROZEN = {
    "main_study_results.csv": "155d28a2d9dc33e11e37f1ae289f221d51d99c239f386a310136c4b84a6844e9",
    "main_study_detection.csv": "c97b5283cbcbafd38aa23949f7025995f4416b0700631388c80095c002a6d8a2",
}
PLACEHOLDER = re.compile(r"\b(TBD|XX|placeholder|lorem ipsum|TODO)\b", re.I)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count(pattern, text):
    return len(re.findall(pattern, text, re.I))


def pdf_pages(path):
    if not path.exists():
        return "missing"
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(m.group(1)) if m else "unknown"


def main():
    ok = True
    print("Frozen artifacts")
    for name, expected in FROZEN.items():
        actual = sha256(HERE / name)
        good = actual == expected
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} {name}: {actual}")

    print("\nNumeric checker")
    chk = subprocess.run(["python3", str(HERE / "check_paper_numbers.py")],
                         capture_output=True, text=True)
    last = [x for x in chk.stdout.strip().splitlines() if "checks passed" in x]
    print(f"  {'PASS' if chk.returncode == 0 else 'FAIL'} {last[-1] if last else 'no checker summary'}")
    ok &= chk.returncode == 0

    for tree in TREES:
        print(f"\n{tree.name}")
        for stem in ("main", "supplement"):
            pdf = tree / f"{stem}.pdf"
            log = tree / f"{stem}.log"
            pages = pdf_pages(pdf)
            print(f"  {stem}: {pages} pages")
            if stem == "main" and isinstance(pages, int) and not 10 <= pages <= 12:
                ok = False
                print(f"    FAIL main PDF outside 10-12 page target")
            if log.exists():
                text = log.read_text(errors="replace")
                undef = count(r"undefined (?:references|reference)", text)
                over = count(r"Overfull \\hbox", text)
                print(f"    undefined references: {undef}; overfull hboxes: {over}")
                ok &= undef == 0 and over == 0
            else:
                print("    log missing")
                ok = False
        for stem in ("main_template.tex", "main.tex", "supplement.tex"):
            path = tree / stem
            if not path.exists():
                continue
            hits = []
            for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
                if line.lstrip().startswith("%"):
                    continue
                if re.search(r"\\newcommand\{\\todo\b", line, re.I):
                    continue  # macro definition, not rendered text
                if PLACEHOLDER.search(line):
                    hits.append(n)
            if hits:
                print(f"    FAIL placeholder tokens in {stem}: {hits}")
                ok = False
        print(f"  PHASE8_INSERT markers: {count(re.escape('% PHASE8_INSERT'), (tree / 'main.tex').read_text(errors='replace'))}"
              if (tree / "main.tex").exists() else "  main.tex missing")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
