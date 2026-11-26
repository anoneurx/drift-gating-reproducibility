# Phase 2: Independent-Replay Oracle — Mathematical Verification

**Target Implementation:** `solveDPOracle()` in `src/pathA_sim.cpp:1129-1190`  
**Audit Branch:** `research-validation-revision`  
**Date:** 2026-11-26

---

## 1. Formulation and Implementation Verification

Let $P = |\mathcal{P}|$ be the number of candidate policies ($P = 21$) and $T = \lfloor (N - N_{\text{warm}}) / W \rfloor$ be the number of complete evaluation windows of length $W$. Under the independent-replay model, each policy $p \in \{0, \dots, P-1\}$ is executed independently over $[0, N_{\text{warm}} + TW)$ with its own cache state, yielding integer per-window miss counts $m_{w,p} \in \{0, \dots, W\}$ for $w = 0, \dots, T-1$.

### 1.1 Recurrence, Initialization, and Terminal Condition

- **Initialization (`src/pathA_sim.cpp:1140`):**
  $$\text{dp}[0][p] = m_{0,p} \quad \forall p \in \{0, \dots, P-1\}.$$
  Initial policy selection at window $0$ incurs zero switching cost.
- **Transition (`src/pathA_sim.cpp:1142-1168`):**
  For $w = 1, \dots, T-1$:
  $$\text{dp}[w][p] = m_{w,p} + \min_{q \in \mathcal{P}} \Bigl(\text{dp}[w-1][q] + c_{\text{switch}} \cdot \mathbf{1}[p \ne q]\Bigr).$$
  The implementation computes `bestQ` and `secondQ` in $\mathcal{O}(P)$ time per window.
  - **Edge case $P = 1$:** `altQ = (bestQ == p && P > 1) ? secondQ : bestQ` evaluates to `0`, so `sw = dp[w-1][0] + c_switch >= stay` for all $c_{\text{switch}} \ge 0$, guaranteeing `stay` is chosen.
  - **Edge case $P \ge 2$ with ties in `dp[w-1]`:** At $q = 0$, `bestV = dp[w-1][0]` (finite) and `secondV = +inf`. For $q \ge 1$, if `dp[w-1][q] == bestV`, the `else if (v < secondV)` branch fires, ensuring `bestQ != secondQ`. Thus `altQ = (bestQ == p) ? secondQ : bestQ` **always** achieves $\min_{q \ne p} \text{dp}[w-1][q]$.
  - **Tie-breaking (`stay <= sw`):** `if (stay <= sw)` chooses `stay` (`par[w][p] = p`), preventing zero-gain switches when `c_switch == 0` or when switching yields exact tie.
- **Terminal selection (`src/pathA_sim.cpp:1170-1173`):**
  $$p_{T-1}^* = \arg\min_{p} \text{dp}[T-1][p],$$
  breaking ties in favor of the lowest policy index in `allPolicyNames()`. Any tied terminal optimum has identical objective value $J^*$.
- **Backtracking & Accounting (`src/pathA_sim.cpp:1174-1189`):**
  Reconstructs `chosen[0..T-1]`, counts `switches = sum_{w=1}^{T-1} 1[chosen[w] != chosen[w-1]]`, and returns:
  $$J^* = \frac{\sum_{w=0}^{T-1} m_{w, \text{chosen}[w]} + S \cdot c_{\text{switch}}}{T \cdot W}.$$
- **Numerical Precision:** All $m_{w,p}$ are integers $\le 10^5$, total misses $\le 2.3 \times 10^6$, and `switchCost` is $\le 10^5$, well within IEEE-754 `double` exact integer representation ($2^{53} \approx 9 \times 10^{15}$). No overflow or catastrophic cancellation occurs.

### 1.2 Exhaustive Brute-Force Verification

`tests/validate_simulator.cpp` compares `solveDPOracle()` against exhaustive $P^T$ enumeration ($P = 4, T = 5$, $1{,}024$ schedules) across $c_{\text{switch}} \in \{0, 15, 35, 100\}$:
- All 4 brute-force checks pass (`abs(dpObj - bfObj) < 1e-12` and identical switch counts).

---

## 2. Is Independent Replay a Universal Upper Bound on Switching Headroom?

**Answer: No — it is exact within the independent-replay model, but NOT a universal mathematical upper bound over arbitrary state-carrying executions.**

### 2.1 Proof by Counterexample ($C = 2$)

Consider two windows with cache capacity $C = 2$ and candidate pool $\{\text{MRU}, \text{LRU}\}$:
- Window 1: $r^{(1)} = (1, 2, 3, 4)$
- Window 2: $r^{(2)} = (1, 4, 5, 4, 5)$

Under **independent replay**:
- `MRU` incurs $4$ misses in $r^{(1)}$ (ending with resident set $\{1, 4\}$) and $3$ misses in $r^{(2)}$ (`1` H, `4` H, `5` M evicting `4`, `4` M evicting `5`, `5` M) $\implies 7$ misses.
- `LRU` incurs $4$ misses in $r^{(1)}$ (ending with resident set $\{3, 4\}$) and $2$ misses in $r^{(2)}$ (`1` M evicting `3`, `4` H, `5` M evicting `1`, `4` H, `5` H) $\implies 6$ misses.
- **Independent-replay DP ($c_{\text{switch}} = 0$):** $\min(4,4) + \min(3,2) = \mathbf{6}$ **misses**.

Under **state-carrying execution (`MRU` $\to$ `LRU`)**:
- `MRU` runs $r^{(1)}$ ($4$ misses), leaving resident set $\{1, 4\}$.
- `switchTo(LRU)` loads $\{1, 4\}$ into `LRU` at the boundary.
- `LRU` runs $r^{(2)}$ starting from $\{1, 4\}$: `1` H, `4` H, `5` M (evicts `1` $\to \{4,5\}$), `4` H, `5` H $\implies \mathbf{1}$ **miss**.
- **State-carrying total:** $4 + 1 = \mathbf{5}$ **misses** $< 6$.

*Verified directly against `src/pathA_sim.cpp` (`mkPolicy`, `load`) on `/tmp/check_oracle_bound.cpp`.*

### 2.2 Theoretical Characterization & Exact Assumptions

Because finite-cache eviction policies are non-additive under arbitrary resident-set perturbations, independent replay is **not** a universal lower bound on misses (upper bound on headroom). Instead, the paper must state precisely what the oracle establishes:

1. **Exact Model-Relative Ceiling:** Within the *independent-replay model* (equivalent to an idealized architecture where every candidate policy maintains a full, warm, un-sampled shadow cache and switching transfers that exact warm state at fixed penalty $c_{\text{switch}}$), `solveDPOracle()` is **mathematically optimal**.
2. **State-Carrying Comparison Condition:** On realistic phase-shifting workloads where heterogeneous `switchTo()` loses ghost lists (`S3-FIFO` ghost, `ARC` $B_1/B_2$, `2Q` $A_{1\text{out}}$) and incurs cold-transition misses, state-carrying execution incurs strictly more misses than independent replay at $c_{\text{switch}} = 0$ (verified on our 3-phase trace: `2,011` state-carrying misses vs. `52` independent-replay $c=0$ misses).
3. **Required Manuscript Revision:** Never describe the oracle as a universal upper bound for all possible real OS implementations; describe it strictly as an **exact hindsight ceiling under the independent-replay model** (and an optimistic benchmark when transitions incur non-negative cold/ghost penalties $\ge c_{\text{switch}}$).
