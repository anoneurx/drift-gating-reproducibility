# Reference verification (2026-11-24)

The reviewer's numbers follow the generated PDFs: main paper `[12]`/`[27]` and
supplement `[41]`. Older source trees number the same entries `[29]`/`[17]`/`[39]`.
No reference was removed; all three were checked against primary sources.

| Reviewer label | Entry | Verification | Action |
|---|---|---|---|
| Main `[12]` (older `[29]`) | Patel & Maniar, *Int. J. Sci. Res. Technol.* 3(6), 556--564, 2026 | DOI <https://doi.org/10.5281/zenodo.20576370> resolves to a Zenodo record with the matching title and authors (Patel Nilen, Himanshu Maniar). The journal landing page <https://ijsrtjournal.com/article/comparative-evaluation-of-cache-replacement-algorithms-for-time-bounded-stale-tolerant-data-workloads> gives volume 3, issue 6, pages 556--564 and the same DOI. | Kept; added both URLs to all bibliography sources. |
| Main `[27]` (older `[17]`) | Yuan et al., EACLOCK, *IEEE TKDE* 38(11), 7387--7401, Nov. 2026 | DOI <https://doi.org/10.1109/TKDE.2026.3724159> resolves with matching title, authors, journal, volume, issue, pages and date. CSDL <https://www.computer.org/csdl/journal/tk/2026/11/11669990/2jk70JkznQ4> and IEEE <https://ieeexplore.ieee.org/document/11669990/> resolve to the same paper. | Kept; added DOI URL and Nov. 2026 issue date to all bibliography sources. |
| Supplement `[41]` (older `[39]`) | CMU PDL, cacheDatasets trace collection | Project page <https://pdl.cmu.edu/CacheEviction/index.shtml> links to <https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/>. The FTP `fiu/` listing contains `fiu_madmax-110108-112108.oracleGeneral.zst`; a direct `curl -sSIL` returned HTTP 200, `Content-Length: 3189409`. The repository README specifies zstd-compressed packed 24-byte request records and four citation papers. | Kept; added exact trace filename, README and copyright URLs to bibliography entries. Narrowed licence wording as described below. |

## PDL trace name and licence scope

Confirmed trace name: `fiu_madmax-110108-112108.oracleGeneral.zst` in the
PDL FTP `fiu/` directory. This is the source file behind the manuscript's
`madmax` label; the reproduction script `reproduction/split_public_traces.py`
lists the six exact FIU source names.

Confirmed licence position:

- The `cacheDatasets/README` has a `Trace format` section and a `Cite` section,
  but no dataset-specific licence file or named dataset licence.
- PDL's site-wide copyright notice at
  <https://pdl.cmu.edu/Publications/copyright.shtml> says documents and/or
  software distributed by the server are provided "on a non-commercial basis",
  that copyright remains with authors or other holders, and that commercial
  redistribution, republication, dissemination or reposting needs explicit
  permission.

The manuscript therefore does **not** say that PDL granted a named dataset
licence. It says that the trace was used for non-commercial research with
citation, and that no dataset-specific licence file was found. This wording is
now used in `drift_gating_latex_source/main.tex`,
`drift_gating_latex_source/supplement.tex`, `paper_final.tex`, `latex/main.tex`
and `latex/supplement.tex`. All manuscript PDF versions were then removed and
replaced by one consolidated deliverable,
`Drift_Aware_Page_Replacement_UPDATED.pdf`, which concatenates the current
11-page main paper and 13-page supplement (24 pages total). Figure PDFs under
`drift_gating_latex_source/figs/` and `reproduction/` are source assets and were
retained.
