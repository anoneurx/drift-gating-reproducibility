# =============================================================================
# Makefile — Drift-Gating Ceiling Study Artifact
# =============================================================================
# Targets
#   build        Compile pathA_sim and real_io_bench
#   test         Run unit tests (policy correctness + DP oracle check)
#   traces       Download and verify public traces
#   oracle       Run hindsight oracle over all traces
#   controllers  Run all 17 switching controllers
#   ablation     Shadow-budget ablation
#   reviewer     Fine cost/window sweep (reviewer additions)
#   tables       Regenerate all LaTeX tables
#   figures      Regenerate all figures
#   pdf          Build the PDF paper
#   all          build + oracle + controllers + ablation + reviewer + tables + figures + pdf
#   verify       Compare regenerated tables to stored baselines (PASS/FAIL)
#   anon         Create anonymised copy in artifact_anonymous/
#   clean        Remove compiled binaries
# =============================================================================

SIM        = src/pathA_sim
BENCH      = src/real_io_bench
SIMCPP     = src/pathA_sim.cpp
BENCHCPP   = src/real_io_bench.cpp
PYTHON     = python3
STUDY      = reproduction/pathA_study
LATEX_DIR  = drift_gating_latex_source

CXX        ?= g++
CXXFLAGS   ?= -O2 -std=c++17 -Wall -Wextra

.PHONY: all build test traces oracle controllers ablation reviewer \
        tables figures pdf verify anon clean

# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
build: $(SIM) $(BENCH)

$(SIM): $(SIMCPP)
	$(CXX) $(CXXFLAGS) -o $@ $<

$(BENCH): $(BENCHCPP)
	$(CXX) $(CXXFLAGS) -o $@ $<

# ---------------------------------------------------------------------------
# test  (unit tests for policy correctness and DP oracle)
# ---------------------------------------------------------------------------
test: build
	$(CXX) $(CXXFLAGS) -o /tmp/validate_sim tests/validate_simulator.cpp && /tmp/validate_sim
	$(PYTHON) tests/run_tests.py

# ---------------------------------------------------------------------------
# traces  (download + SHA-256 verify)
# ---------------------------------------------------------------------------
traces:
	bash scripts/download_traces.sh

# ---------------------------------------------------------------------------
# oracle  (hindsight DP oracle over all 88 traces x 3 caps x 5 windows x 5 costs)
# ---------------------------------------------------------------------------
oracle: build
	$(PYTHON) $(STUDY)/run_study.py --mode oracle

# ---------------------------------------------------------------------------
# controllers  (17 online switching controllers)
# ---------------------------------------------------------------------------
controllers: build
	$(PYTHON) $(STUDY)/run_study.py --mode controllers

# ---------------------------------------------------------------------------
# ablation  (shadow-budget variants)
# ---------------------------------------------------------------------------
ablation: build
	$(PYTHON) $(STUDY)/run_ablation.py

# ---------------------------------------------------------------------------
# reviewer  (fine cost/window sweep + 25%/50% WSS capacities)
# ---------------------------------------------------------------------------
reviewer: build
	$(PYTHON) $(STUDY)/run_reviewer_fixes.py

# ---------------------------------------------------------------------------
# tables + figures  (from CSVs already in results/raw/)
# ---------------------------------------------------------------------------
tables figures: build
	$(PYTHON) $(STUDY)/generate_paper_assets.py

# ---------------------------------------------------------------------------
# pdf  (compile LaTeX → PDF)
# ---------------------------------------------------------------------------
pdf:
	cd $(LATEX_DIR) && $(PYTHON) build.py

# ---------------------------------------------------------------------------
# all
# ---------------------------------------------------------------------------
all: build oracle controllers ablation reviewer tables figures pdf

# ---------------------------------------------------------------------------
# verify  (compare freshly generated tables to stored baselines)
# ---------------------------------------------------------------------------
verify: tables
	$(PYTHON) tests/verify_tables.py

# ---------------------------------------------------------------------------
# anon  (anonymised copy for blind review)
# ---------------------------------------------------------------------------
anon:
	bash scripts/make_anon.sh

# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------
clean:
	rm -f $(SIM) $(BENCH)
