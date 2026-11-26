import re, subprocess, sys

REFS = {
 "arc": r"N. Megiddo and D. S. Modha, ``ARC: A self-tuning, low overhead replacement cache,'' in \emph{Proc. 2nd USENIX Conf. File Storage Technol. (FAST)}, 2003, pp. 115--130.",
 "car": r"S. Bansal and D. S. Modha, ``CAR: Clock with adaptive replacement,'' in \emph{Proc. 3rd USENIX Conf. File Storage Technol. (FAST)}, 2004, pp. 187--200.",
 "lirs": r"S. Jiang and X. Zhang, ``LIRS: An efficient low inter-reference recency set replacement policy to improve buffer cache performance,'' in \emph{Proc. ACM SIGMETRICS}, 2002, pp. 31--42.",
 "twoq": r"T. Johnson and D. Shasha, ``2Q: A low overhead high performance buffer management replacement algorithm,'' in \emph{Proc. 20th Int. Conf. Very Large Data Bases (VLDB)}, 1994, pp. 439--450.",
 "s3fifo": r"J. Yang, Y. Zhang, Z. Qiu, Y. Yue, and K. V. Rashmi, ``FIFO queues are all you need for cache eviction,'' in \emph{Proc. 29th ACM Symp. Oper. Syst. Princ. (SOSP)}, 2023, pp. 130--149.",
 "gama": r"J. Gama, I. \v{Z}liobait\.{e}, A. Bifet, M. Pechenizkiy, and A. Bouchachia, ``A survey on concept drift adaptation,'' \emph{ACM Comput. Surv.}, vol. 46, no. 4, Art. no. 44, 2014.",
 "adwin": r"A. Bifet and R. Gavald\`{a}, ``Learning from time-changing data with adaptive windowing,'' in \emph{Proc. SIAM Int. Conf. Data Mining (SDM)}, 2007, pp. 443--448.",
 "seq": r"G. Glass and P. Cao, ``Adaptive page replacement based on memory reference behavior,'' in \emph{Proc. ACM SIGMETRICS}, 1997, pp. 115--126.",
 "eelru": r"Y. Smaragdakis, S. Kaplan, and P. Wilson, ``EELRU: Simple and effective adaptive page replacement,'' in \emph{Proc. ACM SIGMETRICS}, 1999, pp. 122--133.",
 "acme02": r"I. Ari, A. Amer, R. Gramacy, E. L. Miller, S. A. Brandt, and D. D. E. Long, ``ACME: Adaptive caching using multiple experts,'' in \emph{Proc. Workshop Distrib. Data Struct. (WDAS)}, 2002.",
 "lecar": r"K. Vietri \emph{et al.}, ``Driving cache replacement with ML-based LeCaR,'' in \emph{Proc. 10th USENIX Workshop Hot Topics Storage File Syst. (HotStorage)}, 2018.",
 "cacheus": r"L. V. Rodriguez \emph{et al.}, ``Learning cache replacement with CACHEUS,'' in \emph{Proc. 19th USENIX Conf. File Storage Technol. (FAST)}, 2021, pp. 341--354.",
 "mini": r"C. Waldspurger, T. Saemundsson, I. Ahmad, and N. Park, ``Cache modeling and optimization using miniature simulations,'' in \emph{Proc. USENIX Annu. Tech. Conf. (ATC)}, 2017, pp. 487--498.",
 "shards": r"C. A. Waldspurger, N. Park, A. Garthwaite, and I. Ahmad, ``Efficient MRC construction with SHARDS,'' in \emph{Proc. 13th USENIX Conf. File Storage Technol. (FAST)}, 2015, pp. 95--110.",
 "l3cache": r"W. Zhou, Z. Niu, Y. Xiong, J. Fang, and Q. Wang, ``3L-Cache: Low overhead and precise learning-based eviction policy for caches,'' in \emph{Proc. 23rd USENIX Conf. File Storage Technol. (FAST)}, 2025, pp. 237--254.",
 "lpr": r"H. Kim, ``Learning-based page replacement scheme for efficient I/O processing,'' \emph{Sci. Rep.}, vol. 15, 2025, doi: 10.1038/s41598-025-88736-4.",
 "eaclock": r"G. Yuan, X. Li, S. Wu, Y. Zhu, D. Yang, C. Yao, X. Tang, and G. Chen, ``EACLOCK: An efficient and adaptive page replacement algorithm to understand your workload,'' \emph{IEEE Trans. Knowl. Data Eng.}, vol. 38, no. 11, pp. 7387--7401, Nov. 2026, doi: 10.1109/TKDE.2026.3724159. [Online]. Available: \url{https://doi.org/10.1109/TKDE.2026.3724159}.",
 "clock2q": r"Y. Zhai \emph{et al.}, ``Clock2Q+: A simple and efficient replacement algorithm for metadata cache in VMware vSAN,'' \emph{Proc. VLDB Endow.}, vol. 19, no. 12, pp. 3874--3887, 2026, doi: 10.14778/3827998.3828002.",
 "s4fifo": r"H. Xia, W. Nixon, B. D. Marthen, P. Bhandari, and J. Yang, ``Learning-augmented heuristics: Simple yet smart, robust and interpretable cache eviction,'' in \emph{Proc. 20th USENIX Symp. Oper. Syst. Design Implement. (OSDI)}, 2026, pp. 2241--2259.",
 "lrb": r"Z. Song, D. S. Berger, K. Li, and W. Lloyd, ``Learning relaxed Belady for content distribution network caching,'' in \emph{Proc. 17th USENIX Symp. Networked Syst. Design Implement. (NSDI)}, 2020, pp. 529--544.",
 "hawkeye": r"A. Jain and C. Lin, ``Back to the future: Leveraging Belady's algorithm for improved cache replacement,'' in \emph{Proc. 43rd Int. Symp. Comput. Archit. (ISCA)}, 2016, pp. 78--89.",
 "twitter": r"J. Yang, Y. Yue, and K. V. Rashmi, ``A large scale analysis of hundreds of in-memory cache clusters at Twitter,'' in \emph{Proc. 14th USENIX Symp. Oper. Syst. Design Implement. (OSDI)}, 2020, pp. 191--208.",
 "hedge": r"Y. Freund and R. E. Schapire, ``A decision-theoretic generalization of on-line learning and an application to boosting,'' \emph{J. Comput. Syst. Sci.}, vol. 55, no. 1, pp. 119--139, 1997.",
 "fiu": r"R. Koller and R. Rangaswami, ``I/O deduplication: Utilizing content similarity to improve I/O performance,'' \emph{ACM Trans. Storage}, vol. 6, no. 3, Art. no. 13, 2010.",
 "msched": r"W. Shen, Y. Chen, R. Chen, and H. Chen, ``Towards fully-fledged GPU multitasking via proactive memory scheduling,'' arXiv:2512.24637, 2025.",
 "gpuext": r"Y. Zheng \emph{et al.}, ``gpu\_ext: Extensible OS policies for GPUs via eBPF,'' arXiv:2512.12615, 2025.",
 "page": r"E. S. Page, ``Continuous inspection schemes,'' \emph{Biometrika}, vol. 41, no. 1--2, pp. 100--115, 1954.",
 "msr": r"D. Narayanan, A. Donnelly, and A. Rowstron, ``Write off-loading: Practical power management for enterprise storage,'' \emph{ACM Trans. Storage}, vol. 4, no. 3, Art. no. 10, 2008.",
 "belady": r"L. A. Belady, ``A study of replacement algorithms for a virtual-storage computer,'' \emph{IBM Syst. J.}, vol. 5, no. 2, pp. 78--101, 1966.",
 "wilcoxon": r"F. Wilcoxon, ``Individual comparisons by ranking methods,'' \emph{Biometrics Bull.}, vol. 1, no. 6, pp. 80--83, 1945.",
 "acme": r"T. Azim, A. Nadeem, and A. Ailamaki, ``Adaptive cache mode selection for queries over raw data,'' in \emph{Proc. 9th Int. Workshop Accelerating Analytics Data Manag. Syst. Using Modern Processor Storage Archit. (ADMS@VLDB)}, 2018, pp. 51--65.",
 "holm": r"S. Holm, ``A simple sequentially rejective multiple test procedure,'' \emph{Scand. J. Stat.}, vol. 6, no. 2, pp. 65--70, 1979.",
 "clockpro": r"S. Jiang, F. Chen, and X. Zhang, ``CLOCK-Pro: An effective improvement of the CLOCK replacement,'' in \emph{Proc. USENIX Annu. Tech. Conf. (ATC)}, 2005, pp. 323--336.",
 "dip": r"M. K. Qureshi, A. Jaleel, Y. N. Patt, S. C. Steely Jr., and J. Emer, ``Adaptive insertion policies for high performance caching,'' in \emph{Proc. 34th Int. Symp. Comput. Archit. (ISCA)}, 2007, pp. 381--391, doi: 10.1145/1250662.1250709.",
 "mglru": r"Linux Kernel Organization, ``Multi-gen LRU,'' Linux kernel documentation, 2026. [Online]. Available: \url{https://docs.kernel.org/mm/multigen_lru.html}",
 "pdl": r"CMU Parallel Data Laboratory, ``Cache eviction tactics: cacheDatasets trace collection,'' online data repository and format README, accessed Nov. 24, 2026. The project page links to the \texttt{cacheDatasets} repository; its FIU directory contains \texttt{fiu\_madmax-110108-112108.oracleGeneral.zst}. The README specifies zstd-compressed 24-byte request records and citation requirements, but no dataset-specific licence; PDL's site-wide copyright notice says materials distributed by the server are provided on a non-commercial basis. [Online]. Available: \url{https://pdl.cmu.edu/CacheEviction/index.shtml}; \url{https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/}; \url{https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/README}; \url{https://pdl.cmu.edu/Publications/copyright.shtml}.",
 # added in this revision (cited in the text but missing from the original list); VERIFY details
 "sieve": r"Y. Zhang, J. Yang, Y. Yue, Y. Vigfusson, and K. V. Rashmi, ``SIEVE is simpler than LRU: An efficient turn-key eviction algorithm for web caches,'' in \emph{Proc. 21st USENIX Symp. Networked Syst. Design Implement. (NSDI)}, 2024.",
 "wtinylfu": r"G. Einziger, R. Friedman, and B. Manes, ``TinyLFU: A highly efficient cache admission policy,'' \emph{ACM Trans. Storage}, vol. 13, no. 4, Art. no. 35, 2017.",
 "lhd": r"N. Beckmann, H. Chen, and A. Cidon, ``LHD: Improving cache hit rate by maximizing hit density,'' in \emph{Proc. 15th USENIX Symp. Networked Syst. Design Implement. (NSDI)}, 2018.",
}

src = open("main_template.tex", encoding="utf8").read()
body = src.split("%%BIBLIOGRAPHY%%")[0]
order = []
for m in re.finditer(r"\\cite\{([^}]*)\}", body):
    for k in m.group(1).split(","):
        k = k.strip()
        if k not in order:
            order.append(k)
missing = [k for k in order if k not in REFS]
unused = [k for k in REFS if k not in order]
assert not missing, missing
print("cited:", len(order), "unused:", unused)

bib = "\\begin{thebibliography}{%d}\n\\footnotesize\n\\setlength{\\itemsep}{0pt}\n" % len(order)
for k in order:
    bib += "\\bibitem{%s} %s\n" % (k, REFS[k])
bib += "\\end{thebibliography}\n"
out = src.replace("%%BIBLIOGRAPHY%%", bib)
open("main.tex", "w", encoding="utf8").write(out)
for _ in range(2):
    r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"], capture_output=True)
    if r.returncode != 0:
        print(r.stdout[-3000:].decode("utf8","replace"))
        sys.exit(1)
print("compiled")
