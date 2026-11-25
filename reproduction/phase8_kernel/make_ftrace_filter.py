#!/usr/bin/env python3
"""Select only pre-registered ftrace functions present in this guest kernel."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AVAIL = os.path.join(HERE, "results", "discover", "1", "available_filter_functions.txt")
OUT = os.path.join(HERE, "results", "ftrace_functions.txt")

TARGETS = [
    "handle_mm_fault",
    "do_anonymous_page",
    "do_wp_page",
    "shrink_folio_list",
    "shrink_page_list",
    "reclaim_pages",
    "do_swap_page",
]


def main():
    with open(AVAIL) as fh:
        names = [ln.strip() for ln in fh if ln.strip()]
    chosen = []
    for t in TARGETS:
        matches = [n for n in names if n == t or n.startswith(t + ".") or n.startswith(t + "__")]
        chosen.extend(matches)
    chosen = sorted(set(chosen))
    if not chosen:
        raise SystemExit("no pre-registered ftrace functions available in guest")
    with open(OUT, "w") as fh:
        fh.write("\n".join(chosen) + "\n")
    print(f"selected {len(chosen)} ftrace functions: {', '.join(chosen)}")


if __name__ == "__main__":
    main()
