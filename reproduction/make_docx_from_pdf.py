#!/usr/bin/env python3
"""Create a Word copy whose pages are images of the compiled PDF.

This is a faithful visual copy: every PDF page is rendered at 150 dpi and
embedded as a full-page image.  It is used because the manuscript is compiled
from LaTeX and no native LaTeX-to-DOCX converter is available in the
environment.  Text remains searchable in the accompanying PDF.

Usage: python3 make_docx_from_pdf.py INPUT.pdf OUTPUT.docx
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from docx import Document
from docx.shared import Inches, Pt


def page_size_pdf(pdf):
    out = subprocess.check_output(["pdfinfo", pdf], text=True)
    m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", out)
    if not m:
        raise RuntimeError(f"cannot parse page size from {pdf}")
    return float(m.group(1)), float(m.group(2))


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    pdf, docx_path = sys.argv[1:]
    w_pt, h_pt = page_size_pdf(pdf)
    with tempfile.TemporaryDirectory(prefix="pdf2docx_") as tmp:
        prefix = os.path.join(tmp, "page")
        subprocess.run(["pdftoppm", "-r", "150", "-png", pdf, prefix], check=True)
        pages = sorted(
            os.path.join(tmp, f) for f in os.listdir(tmp) if f.startswith("page-")
        )
        doc = Document()
        sec = doc.sections[0]
        sec.page_width = Pt(w_pt)
        sec.page_height = Pt(h_pt)
        sec.top_margin = Pt(0)
        sec.bottom_margin = Pt(0)
        sec.left_margin = Pt(0)
        sec.right_margin = Pt(0)
        sec.header_distance = Pt(0)
        sec.footer_distance = Pt(0)
        for i, page in enumerate(pages):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run()
            run.add_picture(page, width=Pt(w_pt), height=Pt(h_pt))
            if i != len(pages) - 1:
                doc.add_page_break()
        doc.save(docx_path)
    print(f"Wrote {docx_path} with {len(pages)} full-page images from {pdf}")


if __name__ == "__main__":
    main()
