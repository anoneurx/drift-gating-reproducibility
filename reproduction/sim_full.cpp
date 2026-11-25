// sim.cpp -- INDEPENDENT RE-IMPLEMENTATION of the trace-driven evaluation described in
// "Drift-Aware Adaptive Page Replacement" (Tahir, Qasim, Ahmad). It is written from the
// paper's text (Tables II-V, Eqs. 1-3), NOT from the authors' original source.
// Numbers produced here will NOT match the paper's tables exactly. Where the paper is
// silent, the choice made here is marked "ASSUMPTION".
//
// Build:  g++ -O2 -std=c++17 -o sim sim.cpp
// Run:    ./sim --seed 5001 --out results.csv --det detection.csv [--ablations]
#include <bits/stdc++.h>
using namespace std;
typedef uint32_t u32; typedef uint64_t u64;
static int NP = 1 << 18;  // page-id space; override with --np for large public traces
static int g_phaseOffset = 0;  // references prepended before the first phase boundary
static const u32 NONE = 0xFFFFFFFFu;
// Tunable baseline parameters (ASSUMPTIONS where the paper is silent)
static double g_s3frac = 0.10, g_lirsfrac = 0.10, g_lprthr = 0.05, g_lecarlr = 0.45;
static int g_twoqkin = 0;

struct RNG { mt19937_64 g; RNG(u64 s) : g(s) {}
  double u() { return (g() >> 11) * (1.0 / 9007199254740992.0); }
  u32 n(u32 k) { return (u32)(g() % k); } };

// ---------------------------------------------------------------- workloads
struct Gen { virtual u32 next(RNG&) = 0; virtual ~Gen() {} };
struct ZipfSampler { vector<double> cdf; vector<u32> perm;
  ZipfSampler(int n, double s, RNG& r, bool permute) { cdf.resize(n); double sum = 0;
    for (int i = 0; i < n; i++) { sum += 1.0 / pow(i + 1, s); cdf[i] = sum; }
    for (auto& c : cdf) c /= sum; perm.resize(n); iota(perm.begin(), perm.end(), 0);
    if (permute) shuffle(perm.begin(), perm.end(), r.g); }
  u32 draw(RNG& r) { size_t k = lower_bound(cdf.begin(), cdf.end(), r.u()) - cdf.begin();
    if (k >= perm.size()) k = perm.size() - 1; return perm[k]; } };
struct LoopG : Gen { u32 b, pos = 0; LoopG(u32 b) : b(b) {} u32 next(RNG&) { return b + (pos++ % 1200); } };
struct ZipfG : Gen { u32 b; ZipfSampler z; ZipfG(u32 b, RNG& r) : b(b), z(8000, 0.9, r, true) {}
  u32 next(RNG& r) { return b + z.draw(r); } };
struct HotScanG : Gen { u32 b, pos = 0; HotScanG(u32 b) : b(b) {}
  u32 next(RNG& r) { return r.u() < 0.7 ? b + r.n(600) : b + 600 + (pos++ % 20000); } };
struct WindowG : Gen { u32 b; u64 t = 0; WindowG(u32 b) : b(b) {}
  u32 next(RNG& r) { u32 s = (u32)((t++ / 40) % 20000); return b + (s + r.n(700)) % 20000; } };
struct UniformG : Gen { u32 b; UniformG(u32 b) : b(b) {} u32 next(RNG& r) { return b + r.n(4000); } };
// Kernel models (ASSUMPTION: the paper names five models but gives no parameters)
struct MatrixG : Gen { u32 b, i = 0; MatrixG(u32 b) : b(b) {}
  u32 next(RNG&) { u32 row = i % 40, col = (i / 40) % 40; i++; return b + row * 40 + col; } };
struct HashJoinG : Gen { u32 b, pos = 0; HashJoinG(u32 b) : b(b) {}
  u32 next(RNG& r) { return r.u() < 0.5 ? b + (pos++ % 20000) : b + 20000 + r.n(1500); } };
struct BTreeG : Gen { u32 b; int step = 0; ZipfSampler z; BTreeG(u32 b, RNG& r) : b(b), z(3000, 0.8, r, true) {}
  u32 next(RNG& r) { int s = step++ % 3; if (s == 0) return b; if (s == 1) return b + 1 + r.n(40); return b + 41 + z.draw(r); } };
struct SortG : Gen { u32 b, k = 0; u32 ptr[16] = {0}; SortG(u32 b) : b(b) {}
  u32 next(RNG&) { u32 run = k++ % 16; return b + run * 2500 + (ptr[run]++ % 2500); } };
struct KVG : Gen { u32 b, pos = 0; int burst = 0; ZipfSampler z; KVG(u32 b, RNG& r) : b(b), z(6000, 0.99, r, true) {}
  u32 next(RNG& r) { if (burst > 0) { burst--; return b + 6000 + (pos++ % 20000); }
    if (r.u() < 0.0005) burst = 300; return b + z.draw(r); } };
unique_ptr<Gen> mkPrim(int t, RNG& r) {
  switch (t) { case 0: return make_unique<LoopG>(0); case 1: return make_unique<ZipfG>(2000, r);
    case 2: return make_unique<HotScanG>(10000); case 3: return make_unique<WindowG>(32000);
    default: return make_unique<UniformG>(54000); } }
unique_ptr<Gen> mkKern(int t, RNG& r) {
  switch (t) { case 0: return make_unique<MatrixG>(70000); case 1: return make_unique<HashJoinG>(72000);
    case 2: return make_unique<BTreeG>(95000, r); case 3: return make_unique<SortG>(100000);
    default: return make_unique<KVG>(60000, r); } }
struct Trace { string scen; u64 seed; vector<u32> refs; vector<size_t> bounds; };
Trace genStable(int prim, u64 seed) { RNG r(seed); auto g = mkPrim(prim, r); Trace T{"stable", seed, {}, {}};
  for (int i = 0; i < 300000; i++) T.refs.push_back(g->next(r)); return T; }
Trace genPhased(const string& kind, u64 seed) {
  RNG r(seed); Trace T{kind, seed, {}, {}}; vector<unique_ptr<Gen>> gens; vector<int> seq; int L, R = 0;
  if (kind == "composite") { for (int k = 0; k < 5; k++) gens.push_back(mkKern(k, r)); seq = {0, 1, 2, 3, 4};
    shuffle(seq.begin(), seq.end(), r.g); L = 100000; }
  else { for (int k = 0; k < 5; k++) gens.push_back(mkPrim(k, r));
    if (kind == "recurring") { int a = r.n(5), b2 = (a + 1 + r.n(4)) % 5; seq = {a, b2, a, b2, a, b2}; L = 80000; }
    else { int prev = -1; for (int i = 0; i < 6; i++) { int c; do c = r.n(5); while (c == prev); seq.push_back(c); prev = c; }
      L = 100000; if (kind == "gradual") R = 40000; } }
  int n = seq.size();
  for (int j = 0; j < g_phaseOffset; j++) T.refs.push_back(gens[seq[0]]->next(r));
  for (int i = 0; i < n; i++) { if (i) T.bounds.push_back((size_t)(g_phaseOffset + (size_t)i * L));
    for (int j = 0; j < L; j++) { int g = seq[i];
      if (R) { if (i + 1 < n && j >= L - R / 2) { if (r.u() < (double)(j - (L - R / 2)) / R) g = seq[i + 1]; }
        else if (i > 0 && j < R / 2) { if (r.u() >= 0.5 + (double)j / R) g = seq[i - 1]; } }
      T.refs.push_back(gens[g]->next(r)); } }
  return T; }

// ---------------------------------------------------------------- policies
struct LS { vector<list<u32>> L; vector<list<u32>::iterator> it; vector<int8_t> loc;
  LS(int k) : L(k), it(NP), loc(NP, -1) {}
  void pf(int l, u32 x) { L[l].push_front(x); it[x] = L[l].begin(); loc[x] = l; }
  void rm(u32 x) { L[loc[x]].erase(it[x]); loc[x] = -1; }
  u32 back(int l) { return L[l].back(); } size_t sz(int l) { return L[l].size(); } };
struct Policy { int C; Policy(int c) : C(c) {} virtual ~Policy() {}
  virtual bool access(u32 p) = 0;
  virtual vector<u32> resident() { return {}; }                       // oldest -> newest
  virtual void load(const vector<u32>&, const vector<uint16_t>&) {} };
struct LRU : Policy { LS s; bool mru; LRU(int c, bool m = false) : Policy(c), s(1), mru(m) {}
  bool access(u32 p) override { if (s.loc[p] >= 0) { s.rm(p); s.pf(0, p); return true; }
    if ((int)s.sz(0) >= C) { u32 v = mru ? s.L[0].front() : s.back(0); s.rm(v); } s.pf(0, p); return false; }
  vector<u32> resident() override { return vector<u32>(s.L[0].rbegin(), s.L[0].rend()); }
  void load(const vector<u32>& pg, const vector<uint16_t>&) override { size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
    for (size_t i = st; i < pg.size(); i++) s.pf(0, pg[i]); } };
struct FIFO : Policy { LS s; FIFO(int c) : Policy(c), s(1) {}
  bool access(u32 p) override { if (s.loc[p] >= 0) return true; if ((int)s.sz(0) >= C) s.rm(s.back(0)); s.pf(0, p); return false; } };
struct CLOCK : Policy { vector<u32> fr; vector<char> rb; vector<int> slot; int hand = 0, used = 0;
  CLOCK(int c) : Policy(c), fr(c, NONE), rb(c, 0), slot(NP, -1) {}
  bool access(u32 p) override { if (slot[p] >= 0) { rb[slot[p]] = 1; return true; }
    if (used < C) { fr[used] = p; slot[p] = used; rb[used] = 0; used++; return false; }
    while (rb[hand]) { rb[hand] = 0; hand = (hand + 1) % C; }
    slot[fr[hand]] = -1; fr[hand] = p; slot[p] = hand; rb[hand] = 0; hand = (hand + 1) % C; return false; } };
// LFU with periodic aging; aging period in references (ASSUMPTION: baseline = 4C refs, Table III)
struct LFUA : Policy { set<tuple<u32, u64, u32>> S; vector<u32> cnt, last; vector<char> in; u64 t = 0, age; int n = 0;
  LFUA(int c, u64 ageRefs) : Policy(c), cnt(NP, 0), last(NP, 0), in(NP, 0), age(ageRefs) {}
  bool access(u32 p) override { t++;
    if (age && t % age == 0) { vector<u32> pg; for (auto& e : S) pg.push_back(get<2>(e)); S.clear();
      for (u32 q : pg) { cnt[q] = max<u32>(1, cnt[q] / 2); S.insert({cnt[q], last[q], q}); } }
    if (in[p]) { S.erase({cnt[p], last[p], p}); cnt[p]++; last[p] = t; S.insert({cnt[p], last[p], p}); return true; }
    if (n >= C) { auto v = *S.begin(); S.erase(S.begin()); in[get<2>(v)] = 0; n--; }
    cnt[p] = 1; last[p] = t; in[p] = 1; n++; S.insert({1, t, p}); return false; }
  vector<u32> resident() override { vector<pair<u32, u32>> v; for (auto& e : S) v.push_back({get<1>(e), get<2>(e)});
    sort(v.begin(), v.end()); vector<u32> r; for (auto& x : v) r.push_back(x.second); return r; }
  void load(const vector<u32>& pg, const vector<uint16_t>& c) override { size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
    for (size_t i = st; i < pg.size(); i++) { u32 q = pg[i]; cnt[q] = max<u32>(1, c[i]); last[q] = ++t; in[q] = 1; n++; S.insert({cnt[q], last[q], q}); } } };
struct TwoQ : Policy { LS s; int kin, kout; // lists: 0=A1in 1=Am 2=A1out
  TwoQ(int c) : Policy(c), s(3), kin(g_twoqkin ? g_twoqkin : max(1, c / 4)), kout(max(1, c / 2)) {}
  void reclaim() { if ((int)(s.sz(0) + s.sz(1)) < C) return;
    if ((int)s.sz(0) > kin || s.sz(1) == 0) { u32 v = s.back(0); s.rm(v); s.pf(2, v); if ((int)s.sz(2) > kout) s.rm(s.back(2)); }
    else s.rm(s.back(1)); }
  bool access(u32 p) override { int l = s.loc[p]; if (l == 1) { s.rm(p); s.pf(1, p); return true; } if (l == 0) return true;
    if (l == 2) { s.rm(p); reclaim(); s.pf(1, p); return false; } reclaim(); s.pf(0, p); return false; }
  vector<u32> resident() override { vector<u32> r(s.L[0].rbegin(), s.L[0].rend()); r.insert(r.end(), s.L[1].rbegin(), s.L[1].rend()); return r; }
  void load(const vector<u32>& pg, const vector<uint16_t>& c) override { size_t st = pg.size() > (size_t)C ? pg.size() - C : 0;
    for (size_t i = st; i < pg.size(); i++) s.pf(c[i] >= 2 ? 1 : 0, pg[i]); } };
struct ARC : Policy { LS s; double p = 0; // 0=T1 1=T2 2=B1 3=B2
  ARC(int c) : Policy(c), s(4) {}
  void replace(u32 x) { bool inB2 = s.loc[x] == 3;
    if (s.sz(0) > 0 && ((double)s.sz(0) > p || (inB2 && (double)s.sz(0) == p))) { u32 v = s.back(0); s.rm(v); s.pf(2, v); }
    else if (s.sz(1) > 0) { u32 v = s.back(1); s.rm(v); s.pf(3, v); } }
  bool access(u32 x) override { int l = s.loc[x];
    if (l == 0 || l == 1) { s.rm(x); s.pf(1, x); return true; }
    if (l == 2) { p = min<double>(C, p + max<double>(1, (double)s.sz(3) / s.sz(2))); replace(x); s.rm(x); s.pf(1, x); return false; }
    if (l == 3) { p = max<double>(0, p - max<double>(1, (double)s.sz(2) / s.sz(3))); replace(x); s.rm(x); s.pf(1, x); return false; }
    size_t L1 = s.sz(0) + s.sz(2);
    if ((int)L1 >= C) { if ((int)s.sz(0) < C) { s.rm(s.back(2)); replace(x); } else s.rm(s.back(0)); }
    else { size_t tot = L1 + s.sz(1) + s.sz(3); if ((int)tot >= C) { if ((int)tot >= 2 * C && s.sz(3)) s.rm(s.back(3)); replace(x); } }
    s.pf(0, x); return false; } };
struct S3FIFO : Policy { LS s; int S, M; vector<uint8_t> f; // 0=small 1=main 2=ghost
  S3FIFO(int c) : Policy(c), s(3), f(NP, 0) {
    S = max(1, (int)lround(g_s3frac * c)); M = c - S;
    if (M < 1) { M = max(1, c - 1); S = c - M; }
    if (S < 0) S = 0;
  }
  void evictMain() { while (s.sz(1) > 0) { u32 t = s.back(1); s.rm(t); if (f[t] > 0) { f[t]--; s.pf(1, t); } else return; } }
  void evict() { if ((int)(s.sz(0) + s.sz(1)) < C) return;
    if ((int)s.sz(0) >= S || s.sz(1) == 0) { if (s.sz(0) == 0) { evictMain(); return; } u32 t = s.back(0); s.rm(t);
      if (f[t] > 1 && M > 0) { f[t] = 0; if ((int)s.sz(1) >= M) evictMain(); s.pf(1, t); }
      else { s.pf(2, t); if ((int)s.sz(2) > max(1, M)) s.rm(s.back(2)); } }
    else evictMain(); }
  bool access(u32 x) override { int l = s.loc[x]; if (l == 0 || l == 1) { f[x] = min<int>(3, f[x] + 1); return true; }
    bool g = (l == 2); if (g) s.rm(x); evict(); f[x] = 0; s.pf(g ? 1 : 0, x); return false; } };
struct LeCaR : Policy { LS s; set<tuple<u32, u64, u32>> F; vector<u32> cnt; vector<u64> last, hl, hf; vector<char> hin; // hist: 1=lru 2=lfu
  deque<u32> HL, HF; double wl = 0.5, lr = g_lecarlr, d; u64 t = 0; RNG r;
  LeCaR(int c) : Policy(c), s(1), cnt(NP, 0), last(NP, 0), hl(NP, 0), hf(NP, 0), hin(NP, 0), d(pow(0.005, 1.0 / c)), r(7) {}
  void hist(deque<u32>& H, u32 v, int tag, vector<u64>& tm) { H.push_back(v); tm[v] = t; hin[v] = tag; while ((int)H.size() > C / 2) { u32 o = H.front(); H.pop_front(); if (hin[o] == tag) hin[o] = 0; } }
  bool access(u32 p) override { t++;
    if (s.loc[p] >= 0) { F.erase({cnt[p], last[p], p}); cnt[p]++; last[p] = t; F.insert({cnt[p], last[p], p}); s.rm(p); s.pf(0, p); return true; }
    if (hin[p]) { double rew = pow(d, (double)(t - (hin[p] == 1 ? hl[p] : hf[p])));
      if (hin[p] == 1) wl *= exp(-lr * rew); else wl /= exp(-lr * rew); wl = min(0.99, max(0.01, wl / (wl + (1 - wl)))); hin[p] = 0; }
    if ((int)s.sz(0) >= C) { bool useLRU = r.u() < wl; u32 v;
      if (useLRU) { v = s.back(0); hist(HL, v, 1, hl); } else { v = get<2>(*F.begin()); hist(HF, v, 2, hf); }
      F.erase({cnt[v], last[v], v}); s.rm(v); }
    cnt[p] = 1; last[p] = t; F.insert({1, t, p}); s.pf(0, p); return false; } };
// LPR-style: regret-driven LRU/MRU switching (re-implements the PRINCIPLE of [16], not its code; ASSUMPTION on thresholds)
struct LPR : Policy { LS s; bool mru = false; int epochRefs = 0, ghostHits = 0; int W = 2000; // lists: 0 resident, 1 ghost
  LPR(int c) : Policy(c), s(2) {}
  bool access(u32 p) override {
    if (++epochRefs == W) { if ((double)ghostHits / W > g_lprthr) mru = !mru; ghostHits = 0; epochRefs = 0; while (s.sz(1)) s.rm(s.back(1)); }
    if (s.loc[p] == 0) { s.rm(p); s.pf(0, p); return true; }
    if (s.loc[p] == 1) { ghostHits++; s.rm(p); }
    if ((int)s.sz(0) >= C) { u32 v = mru ? s.L[0].front() : s.back(0); s.rm(v); s.pf(1, v); if ((int)s.sz(1) > 2 * C) s.rm(s.back(1)); }
    s.pf(0, p); return false; } };

// === SIEVE (Zhang et al., NSDI 2024) ===
// Source: "SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web Caches".
// Independent re-implementation from published algorithm description; not authors' code.
struct SIEVE : Policy {
  list<u32> q; // front=newest, back=oldest
  vector<list<u32>::iterator> it; vector<char> in, visited;
  list<u32>::iterator hand; bool handInit = false;
  SIEVE(int c) : Policy(c), it(NP), in(NP,0), visited(NP,0) {}
  bool access(u32 p) override {
    if (in[p]) { visited[p] = 1; return true; }
    if ((int)q.size() >= C) {
      if (!handInit) { hand = prev(q.end()); handInit = true; }
      while (visited[*hand]) { visited[*hand] = 0; hand = (hand == q.begin()) ? prev(q.end()) : prev(hand); }
      u32 v = *hand;
      auto nxt = (hand == q.begin()) ? prev(q.end()) : prev(hand);
      q.erase(hand); in[v] = 0; visited[v] = 0; hand = nxt; if (q.empty()) handInit = false;
    }
    q.push_front(p); it[p] = q.begin(); in[p] = 1; visited[p] = 0;
    return false;
  }
};

// === W-TinyLFU (Einziger et al., FAST 2017) ===
// Simplified independent re-implementation of the W-TinyLFU principle:
// Window LRU + Segmented LRU (probation/protected) + Count-Min Sketch admission.
// Source: Einziger, Friedman, Ben-Zvi, "TinyLFU: A Highly Efficient Cache Admission Policy".
// ASSUMPTIONS: fixed window/protected split (1% window, 19% probation, 80% protected as common config),
// 4-row Count-Min Sketch with simple hash, periodic decay by halving counters every C accesses.
struct WTinyLFU : Policy {
  int Wsz, Psz, ProtSz;
  list<u32> win, prob, prot; // front=MRU
  vector<list<u32>::iterator> itW, itP, itProt;
  vector<char> inW, inP, inProt;
  // Count-Min Sketch
  static const int CMS_D = 4;
  int cmsW;
  vector<uint16_t> cms;
  u64 accesses = 0;
  WTinyLFU(int c) : Policy(c), itW(NP), itP(NP), itProt(NP), inW(NP,0), inP(NP,0), inProt(NP,0) {
    Wsz = max(1, c/100); if (Wsz >= c) Wsz = max(1, c-1);
    int mainC = max(1, c - Wsz);
    ProtSz = max(1, (int)(mainC * 0.8)); Psz = mainC - ProtSz;
    if (Psz < 1) { Psz = 1; ProtSz = max(0, mainC - 1); }
    cmsW = max(1024, c*4); cms.assign(CMS_D * cmsW, 0);
  }
  uint32_t h1(uint32_t x, int i) const { uint64_t z = x + 0x9e3779b97f4a7c15ULL * (i+1); z = (z^(z>>30))*0xbf58476d1ce4e5b9ULL; return (uint32_t)((z^(z>>27)) % cmsW); }
  void cmsInc(u32 x) { for(int i=0;i<CMS_D;i++){ uint32_t idx=i*cmsW+h1(x,i); if(cms[idx]<65535) cms[idx]++; } }
  uint32_t cmsEst(u32 x) const { uint32_t m=65535; for(int i=0;i<CMS_D;i++){ uint32_t v=cms[i*cmsW+h1(x,i)]; if(v<m) m=v; } return m; }
  void cmsDecay() { for (auto &v : cms) v >>= 1; }
  void rmWin(u32 x){ win.erase(itW[x]); inW[x]=0; }
  void rmProb(u32 x){ prob.erase(itP[x]); inP[x]=0; }
  void rmProt(u32 x){ prot.erase(itProt[x]); inProt[x]=0; }
  void addProt(u32 x){ prot.push_front(x); itProt[x]=prot.begin(); inProt[x]=1;
    if ((int)prot.size() > ProtSz) { u32 v=prot.back(); rmProt(v); prob.push_front(v); itP[v]=prob.begin(); inP[v]=1; } }
  void evictProb() { if (!prob.empty()) { u32 v=prob.back(); rmProb(v); } }
  bool access(u32 p) override {
    if (++accesses % (u64)max(1,C) == 0) cmsDecay();
    cmsInc(p);
    if (inW[p]) { win.erase(itW[p]); win.push_front(p); itW[p]=win.begin(); return true; }
    if (inProt[p]) { prot.erase(itProt[p]); prot.push_front(p); itProt[p]=prot.begin(); return true; }
    if (inP[p]) { rmProb(p); addProt(p); return true; }
    // miss: admit to window
    win.push_front(p); itW[p]=win.begin(); inW[p]=1;
    if ((int)win.size() > Wsz) {
      u32 cand = win.back(); rmWin(cand);
      // admit cand to probation/protected? compare against probation victim
      if ((int)(prob.size()+prot.size()) < Psz+ProtSz) {
        prob.push_front(cand); itP[cand]=prob.begin(); inP[cand]=1;
      } else if (!prob.empty()) {
        u32 victim = prob.back();
        if (cmsEst(cand) > cmsEst(victim)) { rmProb(victim); prob.push_front(cand); itP[cand]=prob.begin(); inP[cand]=1; }
        // else cand rejected
      }
    }
    return false;
  }
};

// === LHD-style hit-density heuristic (Beckmann et al., NSDI 2018 inspired) ===
// Source: Beckmann, Chen, Chen, An, "LHD: Improving Cache Hit Rate by Maximizing
// Hit Density", NSDI 2018. INDEPENDENT SIMPLIFICATION, not the authors' code and
// not the paper's exact conditional-probability estimator.  ASSUMPTIONS:
// uniform object size (page/object references carry no size), score =
// (hits + 1) / (age in references + 1), min-score eviction with a lazy heap.
struct LHD : Policy {
  vector<u64> born; vector<uint32_t> hits; vector<char> in; vector<double> key;
  u64 now = 0; int residentN = 0;
  using Key = pair<double, u32>;
  set<Key> order; // score -> object id, always current (no lazy invalidation)
  LHD(int c) : Policy(c), born(NP, 0), hits(NP, 0), in(NP, 0), key(NP, 0) {}
  double score(u32 p) const { return (double)(hits[p] + 1u) / (double)(now - born[p] + 1ull); }
  void add(u32 p) { double s = score(p); order.insert(Key(s, p)); key[p] = s; }
  void remove(u32 p) { order.erase(Key(key[p], p)); }
  bool access(u32 p) override {
    ++now;
    if (in[p]) { remove(p); ++hits[p]; add(p); return true; }
    if (residentN >= C && !order.empty()) {
      auto it = order.begin(); u32 v = it->second; order.erase(it); in[v] = 0; --residentN;
    }
    born[p] = now; hits[p] = 0; in[p] = 1; ++residentN; add(p);
    return false;
  }
};

// === Additional baselines requested by the reviewer ========================
// All are PRINCIPLE-LEVEL independent re-implementations written from the
// published descriptions; ASSUMPTIONS on parameters are marked. They are not
// the authors' code and are not claimed to reproduce published numbers.
struct CAR : Policy { LS s; vector<char> rb; double p = 0;   // 0=T1 1=T2 2=B1 3=B2
  CAR(int c) : Policy(c), s(4), rb(NP, 0) {}
  u32 ev(int l) { while (true) { u32 v = s.back(l); if (rb[v]) { rb[v] = 0; s.rm(v); s.pf(l, v); }
      else { s.rm(v); return v; } } }
  void repl() { if (s.sz(0) && ((double)s.sz(0) > p || (s.sz(0) == p && s.sz(3) > 0))) { u32 v = ev(0); s.pf(2, v); }
    else if (s.sz(1)) { u32 v = ev(1); s.pf(3, v); }
    else if (s.sz(0)) { u32 v = ev(0); s.pf(2, v); } }
  void trim() { while (s.sz(2) + s.sz(3) > (size_t)C) { if (s.sz(2)) s.rm(s.back(2));
      else if (s.sz(3)) s.rm(s.back(3)); else break; } }
  bool access(u32 x) override {
    int l = s.loc[x];
    if (l == 0 || l == 1) { rb[x] = 1; return true; }
    if (l == 2) { p = min<double>(C, p + max<double>(1, (double)s.sz(3) / max<size_t>(1, s.sz(2))));
      if (s.sz(0) + s.sz(1) >= (size_t)C) repl(); s.rm(x); s.pf(1, x); rb[x] = 1; trim(); return false; }
    if (l == 3) { p = max<double>(0.0, p - max<double>(1, (double)s.sz(2) / max<size_t>(1, s.sz(3))));
      if (s.sz(0) + s.sz(1) >= (size_t)C) repl(); s.rm(x); s.pf(1, x); rb[x] = 1; trim(); return false; }
    if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
    s.pf(0, x); rb[x] = 0; trim(); return false; }
};
// LIRS principle: LIR pages are protected, HIR pages are eviction candidates;
// ASSUMPTION: LIR budget = 10% of capacity, recency stack cut below access.
struct LIRS : Policy { struct E { u32 p; bool lir, res; };
  vector<E> st; unordered_map<u32,int> pos; vector<char> resident, islir; deque<u32> R;
  int nres = 0, nLIR = 0, budget;
  LIRS(int c) : Policy(c), resident(NP, 0), islir(NP, 0), budget(max(1, (int)lround(g_lirsfrac * c))) {}
  void moveTop(int i) { if (!i) return; swap(st[0], st[i]); pos[st[0].p] = 0; pos[st[i].p] = i; }
  void cutBelow(int i) { for (int k = (int)st.size() - 1; k > i; k--) pos.erase(st[k].p); st.resize(i + 1); }
  void demote() { for (int k = (int)st.size() - 1; k >= 0 && nLIR > budget; k--)
      if (st[k].lir && islir[st[k].p]) { islir[st[k].p] = 0; nLIR--; st[k].lir = false; } }
  void evict() { if (nres < C) return; while (!R.empty()) { u32 v = R.front(); R.pop_front(); if (!resident[v]) continue;
      resident[v] = 0; nres--; if (islir[v]) { islir[v] = 0; nLIR--; }
      auto it = pos.find(v); if (it != pos.end()) { st[it->second].res = false; st[it->second].lir = false; } return; } }
  bool access(u32 p) override {
    auto it = pos.find(p); bool hit = false;
    if (it == pos.end() && resident[p]) { // resident page evicted from the recency stack
      st.insert(st.begin(), {p, islir[p] != 0, true});
      for (size_t k = 0; k < st.size(); k++) pos[st[k].p] = k;
      hit = true; it = pos.find(p);
      int i = it->second; if (!islir[p]) { islir[p] = 1; nLIR++; } st[i].lir = true;
      moveTop(i); cutBelow(0); }
    else if (it != pos.end()) { int i = it->second; hit = st[i].res;
      if (!st[i].res) { evict(); st[i].res = true; resident[p] = 1; nres++; R.push_back(p); }
      if (!islir[p]) { islir[p] = 1; nLIR++; } st[i].lir = true;
      moveTop(i); cutBelow(0); }
    else { evict(); resident[p] = 1; nres++; R.push_back(p);
      st.insert(st.begin(), {p, false, true}); for (size_t k = 0; k < st.size(); k++) pos[st[k].p] = k; }
    demote(); return hit; }
};
// CLOCK-Pro principle: CLOCK with a second-chance promotion to the protected
// clock and ghost-driven adaptivity. ASSUMPTION: one bit plus one seen bit.
struct CLOCKPro : Policy { LS s; vector<char> rb, seen; double p = 0;
  CLOCKPro(int c) : Policy(c), s(4), rb(NP, 0), seen(NP, 0) {}
  u32 ev(int l) { while (true) { u32 v = s.back(l); if (rb[v]) { rb[v] = 0; s.rm(v); s.pf(l, v); }
      else { s.rm(v); return v; } } }
  void repl() { if (s.sz(0) && ((double)s.sz(0) > p || (s.sz(0) == p && s.sz(3) > 0))) { u32 v = ev(0); s.pf(2, v); }
    else if (s.sz(1)) { u32 v = ev(1); s.pf(3, v); }
    else if (s.sz(0)) { u32 v = ev(0); s.pf(2, v); } }
  void trim() { while (s.sz(2) + s.sz(3) > (size_t)C) { if (s.sz(2)) s.rm(s.back(2));
      else if (s.sz(3)) s.rm(s.back(3)); else break; } }
  bool access(u32 x) override { int l = s.loc[x];
    if (l == 0 || l == 1) { if (seen[x]) { rb[x] = 1; if (l == 0) { s.rm(x); s.pf(1, x); } return true; }
      seen[x] = 1; rb[x] = 1; return true; }
    if (l == 2) { p = min<double>(C, p + 1); repl(); s.rm(x); s.pf(1, x); rb[x] = 1; seen[x] = 1; trim(); return false; }
    if (l == 3) { p = max<double>(0.0, p - 1); repl(); s.rm(x); s.pf(1, x); rb[x] = 1; seen[x] = 1; trim(); return false; }
    if (s.sz(0) + s.sz(1) >= (size_t)C) repl();
    s.pf(0, x); rb[x] = 0; seen[x] = 1; trim(); return false; }
};
// CACHEUS principle: regret-weighted ensemble of LRU / LFU / one-timer experts.
// ASSUMPTION: exponential weight update with decay 0.99.
struct CACHEUS : Policy { LS rec; set<tuple<u32,u64,u32>> F; vector<u64> last, cnt; vector<char> in;
  double w[3] = {1, 1, 1}; u64 t = 0, age; int n = 0;
  CACHEUS(int c) : Policy(c), rec(1), last(NP, 0), cnt(NP, 0), in(NP, 0), age(4ull * c) {}
  bool access(u32 p) override { t++;
    if (t % age == 0) { vector<u32> pg; for (auto& e : F) pg.push_back(get<2>(e)); F.clear();
      for (u32 q : pg) { cnt[q] = max<u64>(1, cnt[q] / 2); F.insert({cnt[q], last[q], q}); } }
    bool hit = in[p];
    if (hit) { F.erase({cnt[p], last[p], p}); cnt[p]++; last[p] = t; F.insert({cnt[p], last[p], p});
      rec.rm(p); rec.pf(0, p); }
    for (int i = 0; i < 3; i++) w[i] = 0.99 * w[i] + (hit ? 0.01 : 0.0);
    if (!hit) { if (n >= C) { int k = (w[0] <= w[1] && w[0] <= w[2]) ? 0 : (w[1] <= w[2] ? 1 : 2);
        u32 v; if (k == 0) v = rec.back(0); else if (k == 1) v = get<2>(*F.begin());
        else { v = rec.back(0); for (auto& e : F) if (get<0>(e) == 1) { v = get<2>(e); break; } }
        F.erase({cnt[v], last[v], v}); rec.rm(v); in[v] = 0; n--; }
      cnt[p] = 1; last[p] = t; in[p] = 1; n++; F.insert({1, t, p}); rec.pf(0, p); }
    return hit; }
};
// 3L-Cache principle (simplified): small recency level, frequency level and
// ghost-protected scan level. ASSUMPTION: 25/50/25 split, one ghost list.
struct ThreeL : Policy { LS s; vector<char> ghost; int n = 0;
  ThreeL(int c) : Policy(c), s(2), ghost(NP, 0) {}
  u32 victim() { if (s.sz(0) > (size_t)(C / 4)) return s.back(0);
    if (s.sz(1) > (size_t)(C / 2)) return s.back(1);
    return s.sz(0) ? s.back(0) : s.back(1); }
  bool access(u32 p) override { int l = s.loc[p];
    if (l >= 0) { s.rm(p); s.pf(1, p); return true; }
    if (ghost[p]) ghost[p] = 0;
    if (n >= C) { u32 v = victim(); s.rm(v); ghost[v] = 1; n--; }
    s.pf(ghost[p] ? 1 : 0, p); n++; return false; }
};


// --- Two further baselines requested in the review -------------------------
// MGLRU-style: multi-generational LRU. ASSUMPTIONS: four generations, an aging
// period of C references, one "seen" bit per page, promotion of generation-0
// pages on aging and demotion of pages without a seen bit. This is a
// page-level abstraction of the Linux multi-gen LRU design, not kernel code.
struct MGLRU : Policy { static const int NG = 4;
  array<list<u32>, NG> L; vector<list<u32>::iterator> it; vector<int8_t> gen, seen; vector<char> in;
  int nres = 0; u64 t = 0; int A;
  MGLRU(int c) : Policy(c), it(NP), gen(NP, -1), seen(NP, 0), in(NP, 0), A(max(1, c)) {}
  void place(u32 p, int g) { L[g].push_front(p); it[p] = L[g].begin(); gen[p] = g; }
  void age() {
    vector<u32> g0(L[0].begin(), L[0].end());
    for (u32 p : g0) { L[0].erase(it[p]); place(p, 1); }
    for (int g = NG - 1; g >= 1; g--) { vector<u32> cur(L[g].begin(), L[g].end());
      for (u32 p : cur) { if (seen[p]) { seen[p] = 0; continue; }
        L[g].erase(it[p]); int ng = min(NG - 1, g + 1);
        L[ng].push_back(p); it[p] = prev(L[ng].end()); gen[p] = ng; } } }
  bool access(u32 p) override { t++;
    if (t % (u64)A == 0) age();
    bool hit = in[p]; if (hit) { seen[p] = 1; L[gen[p]].erase(it[p]); place(p, 0); return true; }
    if (nres >= C) { int g = NG - 1; while (g > 0 && L[g].empty()) g--;
      if (g == 0 && L[0].empty()) g = -1;
      if (g >= 0) { u32 v = L[g].back(); L[g].pop_back(); in[v] = 0; gen[v] = -1; seen[v] = 0; nres--; } }
    place(p, 0); in[p] = 1; seen[p] = 1; nres++; return false; }
};
// Set-dueling adaptive insertion (DIP principle of Qureshi et al., ISCA 2007).
// ASSUMPTIONS: 16 sampler sets by page-id hash; two sampler caches of C/16
// frames following LRU insertion and bimodal (bypass) insertion respectively;
// the sampler with fewer misses over the last C references selects the
// insertion mode for the main cache. On a hit both modes promote to MRU.
struct SetDuel : Policy { static const int NS = 16;
  LS main, sa, sb; int cs, ca; bool bypass = false; u64 t = 0; int W; long long ma = 0, mb = 0;
  SetDuel(int c) : Policy(c), main(1), sa(1), sb(1), cs(c), ca(max(4, c / 16)), W(max(1000, c)) {}
  static void insBypass(LS& s, u32 p) { s.L[0].push_back(p); s.it[p] = prev(s.L[0].end()); s.loc[p] = 0; }
  bool access(u32 p) override { t++;
    if (t % (u64)W == 0) { if (ma > mb) bypass = true; else if (mb > ma) bypass = false; ma = mb = 0; }
    // main cache: always evict LRU end; insertion mode follows the duel winner
    bool hit = main.loc[p] >= 0;
    if (hit) main.rm(p); else if ((int)main.sz(0) >= cs) main.rm(main.back(0));
    if (hit || !bypass) main.pf(0, p); else insBypass(main, p);
    // sampler A (LRU insertion) and sampler B (bimodal insertion)
    if ((p & (NS - 1)) < NS / 2) { if (sa.loc[p] >= 0) sa.rm(p);
      else { ma++; if ((int)sa.sz(0) >= ca) sa.rm(sa.back(0)); } sa.pf(0, p); }
    else { if (sb.loc[p] >= 0) { sb.rm(p); sb.pf(0, p); }
      else { mb++; if ((int)sb.sz(0) >= ca) sb.rm(sb.back(0)); insBypass(sb, p); } }
    return hit; }
};

struct OPT { static double run(const vector<u32>& R, int C, size_t warm) { size_t n = R.size(); vector<u32> nxt(n); unordered_map<u32, u32> lp;
    for (size_t i = n; i-- > 0;) { auto it = lp.find(R[i]); nxt[i] = it == lp.end() ? NONE : it->second; lp[R[i]] = i; }
    set<pair<u32, u32>> S; unordered_map<u32, u32> cur; size_t miss = 0;
    for (size_t i = 0; i < n; i++) { u32 p = R[i]; auto it = cur.find(p);
      if (it != cur.end()) { S.erase({it->second, p}); } else { if (i >= warm) miss++;
        if ((int)cur.size() >= C) { auto v = *S.rbegin(); S.erase(v); cur.erase(v.second); } }
      cur[p] = nxt[i]; S.insert({nxt[i], p}); }
    return (double)miss / (n - warm); } };

// ---------------------------------------------------------------- DA controller
struct Params { int C = 1000, W = 2000, B = 8, minKS = 100, evalDelay = 10, cooldown = 4, dwell = 10, hyst = 30, ageEpochs = 50, contEvery = 10;
  double delta = 0.5, h = 5, alpha = 1e-3, p = 0.2, warm = 0.4, z = 1.28, H = 50000, Kfrac = 0.1; u32 purge = 20000;
  bool useKS = true, useShadow = true, usePurge = true, useCost = true, gated = true;
  // Post hoc capacity-sampling repair (disabled by default for byte-identical
  // reproduction of the pre-specified results).  When csCapF > 0, shadow
  // capacity is capped at min(round(p*C), round(csCapF * D_w)), where D_w is
  // the number of distinct sampled pages in the evaluation window.
  double csCapF = 0.0;
  // Phase 5 robustness (pre-specified): LCB distribution for 4-block decision rule.
  // normal = z*sd/sqrt(4) (default, frozen); t3 = t_{0.90,df=3}*sd/sqrt(4).
  std::string lcbDist = "normal"; // normal|t3
  // Post hoc trigger variants for measurement experiments (default cusum).
  std::string trigger = "cusum"; // cusum|periodic|random|oracle|ph|adwin
  int triggerPeriod = 10;        // epochs, for periodic
  double triggerRand = 0.0;      // per-epoch trigger probability, for random
  u64 triggerSeed = 99;          // RNG seed for random trigger
  // Page-Hinkley params (Phase 3)
  double phDelta = 0.005;
  double phLambda = 5.0;
  // ADWIN param (Phase 3, simplified scalar ADWIN)
  double adwinDelta = 0.002;
  // Optional per-shadow-evaluation diagnostic CSV (Phase 1 rankability).
  std::string evalDiagPath;
};
unique_ptr<Policy> mkCand(int id, int C, u64 ageRefs) { // 0 LRU, 1 LFU-A, 2 2Q, 3 MRU
  if (id == 0) return make_unique<LRU>(C); if (id == 1) return make_unique<LFUA>(C, ageRefs);
  if (id == 2) return make_unique<TwoQ>(C); if (id == 3) return make_unique<LRU>(C, true);
  if (id == 4) return make_unique<S3FIFO>(C); return make_unique<ARC>(C); }
int g_ncand = 6;
double ksP(vector<double> a, vector<double> b) { sort(a.begin(), a.end()); sort(b.begin(), b.end()); size_t i = 0, j = 0; double D = 0;
  while (i < a.size() && j < b.size()) { double x = min(a[i], b[j]); while (i < a.size() && a[i] <= x) i++; while (j < b.size() && b[j] <= x) j++;
    D = max(D, fabs((double)i / a.size() - (double)j / b.size())); }
  double ne = (double)a.size() * b.size() / (a.size() + b.size()), lam = (sqrt(ne) + 0.12 + 0.11 / sqrt(ne)) * D, p = 0;
  for (int k = 1; k <= 100; k++) { double t = 2 * ((k & 1) ? 1 : -1) * exp(-2.0 * k * k * lam * lam); p += t; if (fabs(t) < 1e-10) break; }
  return min(1.0, max(0.0, p)); }
struct SRef { u32 page; int ep; };
struct DA : Policy { Params P; unique_ptr<Policy> act; int actId = 0, prevId = -1; u64 t = 0, ageRefs; int ep = 0, epochRefs = 0, epochMiss = 0;
  enum { BASE, MON, WAIT, COOL } st = BASE; bool firstBase = true; vector<double> bm; double mu = 0, sg = 0.02, Sp = 0, Sn = 0;
  vector<u32> last; vector<uint16_t> cnt; vector<u64> lastS; u64 si = 0; u64 thr; vector<vector<double>> epRu; vector<double> curRu; vector<SRef> win;
  vector<double> baseRu; int confEp = 0, evalAt = 0, coolUntil = 0, lastSwitchEp = -1000; RNG rr;
  vector<u64> confirms; int switches = 0, shadowEvals = 0, alarms = 0; double ksCalls = 0;
  const vector<size_t>* oracleBounds = nullptr; size_t nextBound = 0; RNG trigRng;
  // Page-Hinkley state (Phase 3)
  double phMean = 0.0; long long phN = 0; double phSum = 0.0; double phMin = 0.0;
  // ADWIN state (Phase 3, simplified scalar)
  vector<double> adwinWin;
  ofstream evalDiag;
  bool evalDiagHeader = false;
  DA(const Params& p) : Policy(p.C), P(p), act(mkCand(0, p.C, 4ull * p.C)), ageRefs((u64)p.ageEpochs * p.W), last(NP, 0), cnt(NP, 0), lastS(NP, 0), rr(99), trigRng(p.triggerSeed) {
    thr = (u64)(P.p * 18446744073709551615.0);
    if (!P.evalDiagPath.empty()) {
      evalDiag.open(P.evalDiagPath, ios::out | ios::app);
      if (evalDiag.is_open()) {
        evalDiag.seekp(0, ios::end);
        evalDiagHeader = evalDiag.tellp() > 0;
      }
    }
  }
  void setOracleBounds(const vector<size_t>* b) { oracleBounds = b; nextBound = 0; }
  static u64 hsh(u32 x) { u64 z = x + 0x9e3779b97f4a7c15ULL; z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL; z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL; return z ^ (z >> 31); }
  bool access(u32 p) override { t++; last[p] = (u32)t; if (cnt[p] < 65535) cnt[p]++;
    if (ageRefs && t % ageRefs == 0) for (int i = 0; i < NP; i++) cnt[i] >>= 1;
    bool hit = act->access(p); if (!hit) epochMiss++;
    if (hsh(p) < thr) { si++; double ru = lastS[p] ? (double)(si - lastS[p]) : 1e9; lastS[p] = si; curRu.push_back(ru); win.push_back({p, ep}); }
    if (++epochRefs == P.W) { epochRefs = 0; endEpoch(); } return hit; }
  vector<double> recentRu(int n) { vector<double> r; for (int i = max(0, (int)epRu.size() - n); i < (int)epRu.size(); i++) r.insert(r.end(), epRu[i].begin(), epRu[i].end()); return r; }
  // shadow evaluation: returns per-candidate (miss counts per block); candidates 0..3
  struct Eval { bool ok = false; vector<array<double, 6>> blk; vector<double> tot; double Braw = 0; };
  Eval evaluate(int startEp) { Eval E; vector<u32> w; for (auto& s : win) if (s.ep >= startEp) w.push_back(s.page);
    if (w.size() < 100) return E; int Cs = max(8, (int)lround(P.p * P.C));
    int Dw = 0;
    {
      unordered_set<u32> uniq(w.begin(), w.end());
      Dw = (int)uniq.size();
      if (P.csCapF > 0.0) Cs = min(Cs, max(8, (int)lround(P.csCapF * Dw)));
    }
    size_t wm = (size_t)(w.size() * P.warm), rest = w.size() - wm;
    E.blk.assign(g_ncand, {0,0,0,0,0,0}); E.tot.assign(g_ncand, 0);
    for (int c = 0; c < g_ncand; c++) { auto pol = mkCand(c, Cs, 4ull * Cs);
      for (size_t i = 0; i < w.size(); i++) { bool h = pol->access(w[i]); if (i >= wm && !h) { int b = min<int>(3, (int)((i - wm) * 4 / max<size_t>(1, rest))); E.blk[c][b]++; E.tot[c]++; } } }
    E.Braw = (double)(ep - startEp) * P.W * (1 - P.warm) / 4.0; E.ok = true; shadowEvals++;
    if (evalDiag.is_open()) {
      if (!evalDiagHeader) {
        evalDiag << "ep,startEp,C,W,p,csCapF,Cs,Dw,rankable";
        for (int c = 0; c < g_ncand; c++) evalDiag << ",miss_c" << c;
        evalDiag << "\n";
        evalDiagHeader = true;
      }
      bool rankable = false;
      for (int c = 1; c < g_ncand; c++) { if (E.tot[c] != E.tot[0]) { rankable = true; break; } }
      evalDiag << ep << "," << startEp << "," << P.C << "," << P.W << "," << P.p << "," << P.csCapF << "," << Cs << "," << Dw << "," << (rankable?1:0);
      for (int c = 0; c < g_ncand; c++) evalDiag << "," << E.tot[c];
      evalDiag << "\n";
    }
    return E; }
  int decide(const Eval& E, bool initial) { if (!E.ok) return actId;
    if (initial) { int b = 0; for (int c = 1; c < g_ncand; c++) if (E.tot[c] < E.tot[b]) b = c; return b; }
    double K = P.useCost ? P.Kfrac * P.C : 0, best = 0; int pick = actId;
    for (int c = 0; c < g_ncand; c++) { if (c == actId) continue; double d[4], m = 0; for (int b = 0; b < 4; b++) { d[b] = E.blk[actId][b] - E.blk[c][b]; m += d[b]; } m /= 4;
      double v = 0; for (int b = 0; b < 4; b++) v += (d[b] - m) * (d[b] - m); double sd = sqrt(v / 3);
      double q = (P.lcbDist == "t3") ? 1.6377443536962102 : P.z; // t_{0.90,df=3} or normal z
      double lcb = m - q * sd / 2.0;
      double score = (lcb / P.p / E.Braw) * P.H - K;   // ASSUMPTION: shadow-scale gain divided by p, then by raw refs per block
      if (c == prevId && ep - lastSwitchEp < P.hyst) score -= K;
      if (score > best) { best = score; pick = c; } }
    return pick; }
  void switchTo(int id) { if (id == actId) return; auto pg = act->resident(); sort(pg.begin(), pg.end(), [&](u32 a, u32 b) { return last[a] < last[b]; });
    if (P.usePurge) { vector<u32> k; for (u32 q : pg) if (t - last[q] <= P.purge) k.push_back(q); pg.swap(k); }
    vector<uint16_t> c; for (u32 q : pg) c.push_back(cnt[q]); auto np = mkCand(id, P.C, 4ull * P.C); np->load(pg, c); act = move(np);
    if (getenv("DA_DEBUG")) fprintf(stderr, "t=%llu ep=%d %d->%d kept=%zu\n", (unsigned long long)t, ep, actId, id, pg.size());
    prevId = actId; actId = id; lastSwitchEp = ep; switches++; }
  void endEpoch() { double m = (double)epochMiss / P.W; epochMiss = 0; ep++; epRu.push_back(curRu); curRu.clear();
    if (epRu.size() > 60) epRu.erase(epRu.begin()); while (!win.empty() && win.front().ep < ep - 45) win.erase(win.begin(), win.begin() + min<size_t>(win.size(), 20000));
    if (st == BASE) { bm.push_back(m); if ((int)bm.size() == P.B) { double s = 0; for (double x : bm) s += x; mu = s / bm.size(); double v = 0; for (double x : bm) v += (x - mu) * (x - mu);
        sg = max(0.02, sqrt(v / bm.size())); Sp = Sn = 0; baseRu = recentRu(P.B);
        if (firstBase) { firstBase = false; if (P.useShadow) switchTo(decide(evaluate(ep - P.B), true)); }
        st = MON; phMean = 0.0; phN = 0; phSum = 0.0; phMin = 0.0; adwinWin.clear(); } return; }
    if (!P.gated) { if (ep % P.contEvery == 0) { if (P.useShadow) switchTo(decide(evaluate(ep - P.contEvery), false)); } return; }
    if (st == MON) {
      bool fired = false; u64 fireRef = t;
      if (P.trigger == "cusum") {
        double z = (m - mu) / sg; Sp = max(0.0, Sp + z - P.delta); Sn = max(0.0, Sn - z - P.delta);
        if (Sp > P.h || Sn > P.h) { alarms++; bool ok = true;
          if (P.useKS) { auto rc = recentRu(3); ok = rc.size() >= (size_t)P.minKS && baseRu.size() >= (size_t)P.minKS && ksP(baseRu, rc) < P.alpha; }
          if (ok) { fired = true; } else Sp = Sn = 0; }
      } else if (P.trigger == "periodic") {
        if (P.triggerPeriod > 0 && ep % P.triggerPeriod == 0) { alarms++; fired = true; }
      } else if (P.trigger == "random") {
        if (P.triggerRand > 0.0 && trigRng.u() < P.triggerRand) { alarms++; fired = true; }
      } else if (P.trigger == "oracle") {
        if (oracleBounds) {
          while (nextBound < oracleBounds->size() && (*oracleBounds)[nextBound] < (size_t)(t > (u64)P.W ? t - P.W : 0)) nextBound++;
          if (nextBound < oracleBounds->size() && (*oracleBounds)[nextBound] < (size_t)t) { alarms++; fired = true; fireRef = (*oracleBounds)[nextBound]; nextBound++; }
        }
      } else if (P.trigger == "ph") {
        // Page-Hinkley (Phase 3): standard cumulative mean-deviation test on epoch miss ratio.
        phN++; phMean += (m - phMean) / (double)phN;
        phSum += (m - phMean - P.phDelta);
        if (phSum < phMin) phMin = phSum;
        if (phSum - phMin > P.phLambda) { alarms++; fired = true; phMean = 0.0; phN = 0; phSum = 0.0; phMin = 0.0; }
      } else if (P.trigger == "adwin") {
        // Simplified scalar ADWIN (Phase 3, Bifet & Gavalda 2007 inspired):
        // buffer epoch miss ratios; test all cuts for Hoeffding bound; on alarm drop older window.
        adwinWin.push_back(m);
        if (adwinWin.size() > 200) adwinWin.erase(adwinWin.begin(), adwinWin.begin() + (adwinWin.size() - 200));
        bool adwinFired = false;
        size_t n = adwinWin.size();
        if (n >= 10) {
          double total = 0; for (double x : adwinWin) total += x;
          double sum0 = 0;
          for (size_t cut = 1; cut < n; cut++) {
            sum0 += adwinWin[cut-1];
            size_t n0 = cut, n1 = n - cut;
            if (n0 < 5 || n1 < 5) continue;
            double mu0 = sum0 / n0, mu1 = (total - sum0) / n1;
            double mH = 1.0 / (1.0/n0 + 1.0/n1); // harmonic mean
            double eps = sqrt(1.0 / (2.0 * mH) * log(4.0 * (double)n / max(1e-12, P.adwinDelta)));
            if (fabs(mu0 - mu1) > eps) { adwinFired = true; adwinWin.erase(adwinWin.begin(), adwinWin.begin() + cut); break; }
          }
        }
        if (adwinFired) { alarms++; fired = true; }
      } else { // unknown trigger, fall back to cusum
        double z = (m - mu) / sg; Sp = max(0.0, Sp + z - P.delta); Sn = max(0.0, Sn - z - P.delta);
        if (Sp > P.h || Sn > P.h) { alarms++; bool ok = true;
          if (P.useKS) { auto rc = recentRu(3); ok = rc.size() >= (size_t)P.minKS && baseRu.size() >= (size_t)P.minKS && ksP(baseRu, rc) < P.alpha; }
          if (ok) { fired = true; } else Sp = Sn = 0; }
      }
      if (fired) { confirms.push_back(fireRef); confEp = ep; evalAt = ep + P.evalDelay; st = WAIT; Sp = Sn = 0; }
      return; }
    if (st == WAIT) { if (ep >= evalAt) { int pick = actId;
        if (!P.useShadow) { do pick = rr.n(4); while (pick == actId); } else pick = decide(evaluate(confEp), false);
        if (ep - lastSwitchEp >= P.dwell) switchTo(pick); st = COOL; coolUntil = ep + P.cooldown; } return; }
    if (st == COOL) { if (ep >= coolUntil) { st = BASE; bm.clear(); } } }
};

// ---------------------------------------------------------------- harness
struct Res { double miss = 0, ns = 0; int sw = 0, ev = 0; vector<u64> conf; };
Res runPolicy(Policy* p, const Trace& T, size_t warm) { auto t0 = chrono::steady_clock::now(); size_t miss = 0;
  for (size_t i = 0; i < T.refs.size(); i++) { bool h = p->access(T.refs[i]); if (i >= warm && !h) miss++; }
  double ns = chrono::duration<double, nano>(chrono::steady_clock::now() - t0).count() / T.refs.size();
  Res r; r.miss = (double)miss / (T.refs.size() - warm); r.ns = ns; return r; }
int main(int argc, char** argv) {
  u64 seed = 5001; string out = "results.csv", det = "detection.csv", methods_arg; bool abl = false, daonly = false; Params P; int nper = 20, nstable = 6; size_t warm = 20000; vector<string> tfiles;
  for (int i = 1; i < argc; i++) { string a = argv[i]; auto nx = [&]() { return string(argv[++i]); };
    if (a == "--seed") seed = stoull(nx()); else if (a == "--out") out = nx(); else if (a == "--det") det = nx(); else if (a == "--ablations") abl = true;
    else if (a == "--da-only") daonly = true;
    else if (a == "--methods") methods_arg = nx();
    else if (a == "--C") P.C = stoi(nx()); else if (a == "--h") P.h = stod(nx()); else if (a == "--delta") P.delta = stod(nx()); else if (a == "--alpha") P.alpha = stod(nx()); else if (a == "--p") P.p = stod(nx());
    else if (a == "--kfrac") P.Kfrac = stod(nx());
    else if (a == "--ncand") g_ncand = stoi(nx());
    else if (a == "--z") P.z = stod(nx());
    else if (a == "--H") P.H = stod(nx());
    else if (a == "--edelay") P.evalDelay = stoi(nx());
    else if (a == "--cs-cap-f") P.csCapF = stod(nx());
    else if (a == "--lcb-dist") P.lcbDist = nx();
    else if (a == "--eval-diag") P.evalDiagPath = nx();
    else if (a == "--trigger") P.trigger = nx();
    else if (a == "--trigger-period") P.triggerPeriod = stoi(nx());
    else if (a == "--trigger-rand") P.triggerRand = stod(nx());
    else if (a == "--trigger-seed") P.triggerSeed = stoull(nx());
    else if (a == "--ph-delta") P.phDelta = stod(nx());
    else if (a == "--ph-lambda") P.phLambda = stod(nx());
    else if (a == "--adwin-delta") P.adwinDelta = stod(nx());
    else if (a == "--trace") tfiles.push_back(nx());
    else if (a == "--np") NP = stoi(nx());
    else if (a == "--phase-offset") g_phaseOffset = stoi(nx());
    else if (a == "--warm") warm = stoull(nx());
    else if (a == "--s3frac") g_s3frac = stod(nx());
    else if (a == "--lirsfrac") g_lirsfrac = stod(nx());
    else if (a == "--lprthr") g_lprthr = stod(nx());
    else if (a == "--lecarlr") g_lecarlr = stod(nx());
    else if (a == "--twoqkin") g_twoqkin = stoi(nx());
    else if (a == "--W") P.W = stoi(nx()); else if (a == "--per-scenario") nper = stoi(nx()); else if (a == "--stable-per-prim") nstable = stoi(nx());
    else if (a.rfind("traces_real/", 0) == 0) tfiles.push_back(a);
    else { fprintf(stderr, "unknown arg %s\n", a.c_str()); return 1; } }
  set<string> want;
  { string cur; for (char ch : methods_arg + ",") { if (ch == ',') { if (!cur.empty()) want.insert(cur); cur.clear(); } else cur += ch; } }
  vector<Trace> traces;
  if (!tfiles.empty()) {
    if (warm == 20000) warm = 100000;
    for (auto& f : tfiles) { ifstream in(f, ios::binary); Trace T{"real", 0, {}, {}};
      string nm = f; size_t sl = nm.find_last_of('/'); if (sl != string::npos) nm = nm.substr(sl + 1);
      if (nm.size() > 4 && nm.substr(nm.size() - 4) == ".bin") nm = nm.substr(0, nm.size() - 4);
      T.scen = "real-" + nm; u32 v; while (in.read((char*)&v, sizeof(v))) T.refs.push_back(v);
      T.seed = traces.size(); traces.push_back(T); } }
  else {
  for (int pr = 0; pr < 5; pr++) for (int k = 0; k < nstable; k++) traces.push_back(genStable(pr, seed + pr * 100 + k));
  const char* sc[] = {"abrupt", "gradual", "recurring", "composite"}; for (int s = 0; s < 4; s++) for (int k = 0; k < nper; k++) traces.push_back(genPhased(sc[s], seed + 1000 * (s + 1) + k));
  }
  ofstream fo(out), fd(det); fo << "scenario,seed,method,miss_ratio,switches,shadow_evals,ns_per_ref\n"; fd << "scenario,seed,method,n_bounds,detected,delays,spurious,confirms,false_after_100k\n";
  int C = P.C; fprintf(stderr, "%zu traces\n", traces.size());
  for (auto& T : traces) { auto emit = [&](const string& name, Res r) { fo << T.scen << ',' << T.seed << ',' << name << ',' << fixed << setprecision(5) << r.miss << ',' << r.sw << ',' << r.ev << ',' << setprecision(1) << r.ns << '\n'; };
    vector<pair<string, function<unique_ptr<Policy>()>>> M = {{"LRU", [&] { return make_unique<LRU>(C); }}, {"FIFO", [&] { return make_unique<FIFO>(C); }}, {"CLOCK", [&] { return make_unique<CLOCK>(C); }},
      {"LFU-A", [&] { return make_unique<LFUA>(C, 4ull * C); }}, {"MRU", [&] { return make_unique<LRU>(C, true); }}, {"2Q", [&] { return make_unique<TwoQ>(C); }}, {"ARC", [&] { return make_unique<ARC>(C); }},
      {"S3-FIFO", [&] { return make_unique<S3FIFO>(C); }}, {"LeCaR", [&] { return make_unique<LeCaR>(C); }}, {"LPR-style", [&] { return make_unique<LPR>(C); }},
      {"SIEVE", [&] { return make_unique<SIEVE>(C); }}, {"W-TinyLFU", [&] { return make_unique<WTinyLFU>(C); }}, {"LHD", [&] { return make_unique<LHD>(C); }},
      {"CAR", [&] { return make_unique<CAR>(C); }}, {"LIRS", [&] { return make_unique<LIRS>(C); }}, {"CLOCK-Pro", [&] { return make_unique<CLOCKPro>(C); }},
      {"CACHEUS", [&] { return make_unique<CACHEUS>(C); }}, {"3L-style", [&] { return make_unique<ThreeL>(C); }},
      {"MGLRU-style", [&] { return make_unique<MGLRU>(C); }}, {"DIP-set-duel", [&] { return make_unique<SetDuel>(C); }}};
    if (!daonly) { for (auto& m : M) { if (!want.empty() && !want.count(m.first)) continue; auto p = m.second(); emit(m.first, runPolicy(p.get(), T, warm)); } }
    vector<pair<string, Params>> V; Params q = P; std::string daName = (q.trigger=="cusum"?"DA":std::string("DA-")+q.trigger); V.push_back({daName, q});
    if (!daonly && (want.empty() || want.count("ContShadow"))) { q = P; q.gated = false; V.push_back({"ContShadow", q}); }
    if (abl) { q = P; q.usePurge = false; V.push_back({"DA-noPurge", q}); q = P; q.useKS = false; V.push_back({"DA-noS2", q}); q = P; q.useShadow = false; V.push_back({"DA-noShadow", q});
      q = P; q.useCost = false; V.push_back({"DA-noCost", q}); q = P; q.dwell = 0; V.push_back({"DA-noDwell", q}); }
    for (auto& v : V) { DA d(v.second); d.setOracleBounds(&T.bounds); Res r = runPolicy(&d, T, warm); r.sw = d.switches; r.ev = d.shadowEvals; emit(v.first, r);
      if (v.first.rfind("DA",0)==0) { int nb = T.bounds.size(), detc = 0, spur = 0, f100 = 0; string dl;
        for (u64 c : d.confirms) { bool in = false; for (size_t b : T.bounds) if (c >= b && c <= b + 30000) in = true; if (!in) spur++; if (T.scen == "stable" && c > 100000) f100++; }
        for (size_t b : T.bounds) { u64 best = 0; bool f = false; for (u64 c : d.confirms) if (c >= b && c <= b + 30000) { best = c - b; f = true; break; } if (f) { detc++; dl += to_string(best) + ";"; } }
        fd << T.scen << ',' << T.seed << ",DA," << nb << ',' << detc << ',' << dl << ',' << spur << ',' << d.confirms.size() << ',' << f100 << '\n'; } }
    if (!daonly && (want.empty() || want.count("OPT"))) emit("OPT", Res{OPT::run(T.refs, C, warm), 0, 0, 0, {}}); fprintf(stderr, "."); }
  fprintf(stderr, "\ndone\n"); return 0; }
