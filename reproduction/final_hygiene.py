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
FIRST_COMMIT = "8d69a4667ca71a05b79034180b7e42766cfaa66a"
AFFIRMATIVE = [
    "pre-specified", "pre-registered", "protocol-guided",
    "registered in `PROTOCOL.md` before", "before affected runs",
    "fixed before inspection", "recorded before execution",
    "date pre-specified",
]
POSTHOC_SOURCES = [
    "latex/main.tex", "latex/supplement.tex", "paper_final.tex",
    "drift_gating_latex_source/main_template.tex",
    "drift_gating_latex_source/main.tex",
    "drift_gating_latex_source/supplement.tex",
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count(pattern, text):
    return len(re.findall(pattern, text, re.I))


def git_text(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True).stdout.strip()


def pdf_text(path):
    if not path.exists():
        return ""
    return subprocess.run(["pdftotext", str(path), "-"], capture_output=True,
                          text=True).stdout


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

    print("\nPost hoc evidentiary status")
    for rel in POSTHOC_SOURCES:
        txt = (ROOT / rel).read_text(errors="replace")
        low = txt.lower()
        hits = [phrase for phrase in AFFIRMATIVE if phrase in low]
        good = not hits and "post hoc" in low
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} {rel}: "
              f"{'post hoc only' if good else 'affirmative=' + ','.join(hits) if hits else 'missing post hoc'}")
    protocol = (ROOT / "PROTOCOL.md").read_text(errors="replace")
    plow = protocol.lower()
    good = all(x in protocol for x in (
        "## Version history and evidentiary status",
        FIRST_COMMIT,
        "No independently timestamped version")) and "**post hoc**" in plow
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'} PROTOCOL.md: version history + post hoc status")
    for tree in TREES:
        txt = pdf_text(tree / "main.pdf").lower()
        hits = [phrase for phrase in AFFIRMATIVE if phrase in txt]
        good = "post hoc" in txt and not hits
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} {tree.name}/main.pdf: "
              f"{'post hoc wording in compiled PDF' if good else 'stale or missing wording'}")

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

    print("\nGit provenance")
    commits = [line.split(" ", 1) for line in
               git_text("log", "--reverse", "--format=%H %cI").splitlines() if line]
    good = len(commits) >= 3
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'} commit count: {len(commits)} (>= 3 required)")
    if commits:
        good = commits[0][0] == FIRST_COMMIT and commits[0][1].startswith("2026-11-24")
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'} first commit: {commits[0][0]} {commits[0][1]}")
    head_date = git_text("log", "-1", "--format=%cI")
    good = head_date.startswith("2026-11-24")
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'} HEAD date: {head_date or 'missing'}")
    status = git_text("status", "--porcelain")
    good = status == ""
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'} clean working tree: {'yes' if good else status[:120]}")
    hashes = set(re.findall(r"\b[0-9a-f]{40}\b", protocol))
    good = FIRST_COMMIT in hashes and len(hashes) >= 2
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'} PROTOCOL.md records {len(hashes)} commit hash(es)")
    tag = git_text("tag", "-l", "v1.0-posthoc")
    good = tag == "v1.0-posthoc"
    ok &= good
    print(f"  {'PASS' if good else 'FAIL'} annotated tag v1.0-posthoc: {'present' if good else 'missing'}")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
