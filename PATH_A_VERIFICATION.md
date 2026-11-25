# Verified Path A evidence package

**Verification timestamp (UTC):** 2026-11-25T17:20:05Z  
**Local research tree:** `/home/kashie/Sem 5/research`  
**Public tree:** `/home/kashie/Sem 5/blackwall-rust`  
**Method:** read-only checks against committed CSVs, protocols, result memos, and paper draft. No trace was regenerated, converted, or modified during verification.

## Verification commands

```sh
python3 reproduction/pathA_oracle/verify_pathA_evidence.py
python3 reproduction/pathA_oracle/verify_pathA_evidence.py \
  --public-root "/home/kashie/Sem 5/blackwall-rust"
python3 reproduction/final_hygiene.py
```

Results:

| Check | Result |
|---|---|
| `verify_pathA_evidence.py` on research tree | **PASS (63 checks passed)** |
| `verify_pathA_evidence.py --public-root ...` | **PASS (80 checks passed)** |
| `final_hygiene.py` after committing these files | **PASS** |
| Raw checker on `results/` | `FAILURES: 0` |
| Raw checker on `results_w100000/` | `FAILURES: 0` |
| Raw checker on `results_extension/` | `FAILURES: 0` |

Full logs are outside the repository in `/home/kashie/Tmp/research/pathA_verify/`:
`research_verify.txt`, `public_sync_verify.txt`, and `final_hygiene.txt`.
Manuscript rebuild logs are in `/home/kashie/Tmp/research/pdf_update/`, including
`docx_convert_latest.log`.

## Verified primary run (`reproduction/pathA_oracle/results/`)

| Verified claim | Value |
|---|---|
| Source manifest traces | 78 |
| Summary / policy / window rows | 468 / 4,680 / 1,542 |
| Family-capacity groups | 117 charged, 117 zero-cost |
| Charged decision | `PATH_A_DECISIVE_NEGATIVE` |
| Charged groups meeting bar | 0/117 |
| Largest charged family-mean gain | 0.01355 |
| Mean charged row gain | -0.00130 |
| Zero-cost groups meeting bar | 3/117 |
| Largest zero-cost family-mean gain | 0.05616 |
| Rows where S3-FIFO is best static | 101/234 |

## Verified sensitivity run (`reproduction/pathA_oracle/results_w100000/`)

| Verified claim | Value |
|---|---|
| Summary / policy / window rows | 468 / 4,680 / 663 |
| Decision | `PATH_B_GATE` |
| Gate group | `fiu_online.cs.fiu.edu|C=15539|W=100000` |
| Charged / zero-cost groups meeting bar | 1/117 / 1/117 |
| Gate trace | `fiu_online.cs.fiu.edu_test` |
| Gate capacity / window | 15,539 / 100,000 |
| Gate charged gain | 0.04449 |
| Gate oracle switches | 2 |

## Verified extension (`reproduction/pathA_oracle/results_extension/`)

| Verified claim | Value |
|---|---|
| Manifest traces | 10 |
| Summary / policy / window rows | 120 / 1,200 / 1,347 |
| Family-capacity groups | 60 |
| Decision | `PATH_A_STANDS` |
| Distinct FIU-online replicas required / found | 2 / 1 |
| Replica trace | `fiu_online_seg1p5m_2m` |
| Unseen-family groups required / found | 1 / 0 |
| Charged groups meeting bar | 2/60 at 50,000; 1/60 at 100,000 |
| Zero-cost groups meeting bar | 9/60 at 50,000; 4/60 at 100,000 |
| Mean charged row gain | -0.00595 |
| Mean zero-cost row gain | 0.01085 |
| Rows where S3-FIFO is best static | 30/60 |
| Distinct best policies | 6 |
| `fiu_madmax_2m` actual `ref_stop` | 918,010 |
| Manifest source/bin hashes and source URLs | 64-hex hashes; PDL FIU base URL |

## Verified protocol and wording

- Primary protocol records `2026-11-25T09:25:44Z` and local HEAD `d54b0d959480062d3948a2b9ac70b42341894238`.
- Extension protocol records `2026-11-25T10:08:54Z` and local HEAD `ffc9f3768ef9a1e066d8077d80f67be26779faa7`.
- Amendment 1 records `2026-11-25T16:36:57Z` before the extension oracle run.
- PDL wording is exact: “Use is non-commercial research with citation; raw traces are not redistributed.” No dataset-specific licence is claimed.
- Both `PATH_A_EXTENSION_RESULTS.md` and `PATH_A_SHORT_PAPER.md` report `PATH_A_STANDS`.

## Verified publication state

- All 16 shared Path A markdown, script, and extension CSV files are byte-identical between the research tree and the public tree.
- The public repo contains no `.zst`, `.bin`, PDF, or DOCX files.
- `final_hygiene.py` confirms frozen main-study hashes, `509/509` numeric checks, a 24-page unified PDF, zero undefined references, zero overfull hboxes, and a clean working tree.

## Verified manuscript PDF and editable DOCX update

**Update verification timestamp (UTC):** 2026-11-25T18:00:46Z

The authoritative LaTeX sources were edited additively to report the verified
extension decision; no Path A CSV, script, protocol, or result memo was changed.
`drift_gating_latex_source/main.pdf` rebuilt at 11 pages and
`drift_gating_latex_source/supplement.pdf` rebuilt at 13 pages, then
`pdfunite` produced `Drift_Aware_Page_Replacement_UPDATED.pdf` at 24 pages.

```sh
pdftotext Drift_Aware_Page_Replacement_UPDATED.pdf - | grep -nE \
  'PATH_A_STANDS|0/117|1/117|0\.01355|0\.04449|0\.00595'
```

Verified PDF text contains `PATH_A_STANDS`, `0/117`, `1/117`, `0.01355`,
`0.04449`, and `−0.00595` (the PDF text extractor renders the minus as a
Unicode sign). The unified PDF still passes the post hoc wording check and has
zero banned affirmative phrases.

The editable Word copy was regenerated from that PDF with pdf2docx 0.5.13,
installed only under `/home/kashie/Tmp/pdf2docx_env_latest`. Conversion logs
show all 24 pages parsed and created with no ignored pages. `python-docx`
verifies editable text rather than page images: 669 paragraphs, 82 tables,
0 inline shapes, and the same Path A tokens are present in the document text.

## Scope of this verification

This check verifies traceability and internal consistency of the Path A package. It does not add evidence for Path B. The still-open limitations remain: no recent learned-policy baseline, no libCacheSim cross-check, no native VM page traces, no kernel/end-to-end system result, and no held-out-family predictive rule.
