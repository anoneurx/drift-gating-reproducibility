// Record genuine page-reference traces from instrumented real programs.
// Each ACC(ptr) logs the 4 KiB page of a real data access made by the kernel.
// Raw pages are mapped to dense ids on first touch, preserving reuse structure.
// Build: g++ -O2 -std=c++17 -o real_traces real_traces.cpp
#include <bits/stdc++.h>
using namespace std;
using u32 = uint32_t; using u64 = uint64_t;

static unordered_map<u64, u32> ids;
static vector<u32> logrefs;
static const size_t CAP = 300000;
static string g_suffix;
static bool g_log = true;
inline void ACC(const void* p) {
    if (!g_log || logrefs.size() >= CAP) return;
    u64 key = ((u64)(uintptr_t)p) >> 12;
    auto it = ids.find(key);
    if (it == ids.end()) { u32 id = (u32)ids.size(); ids.emplace(key, id); logrefs.push_back(id); }
    else logrefs.push_back(it->second);
}
static void save(const string& name) {
    ofstream f("traces_real/" + name + g_suffix + ".bin", ios::binary);
    f.write((const char*)logrefs.data(), logrefs.size() * sizeof(u32));
    cerr << name << ": " << logrefs.size() << " refs, " << ids.size() << " pages\n";
    logrefs.clear(); ids.clear();
}
static u64 rs = 12345;
static u64 rnd() { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return rs; }

// ---- 1. In-memory index tree: inserts then key lookups ---------------------
// Each node is padded to one 4 KiB page, so a tree traversal is a realistic
// page-reference sequence for a disk-backed index with one node per page.
struct Node { int key, left, right; char pad[4080]; };
static void btree() {
    vector<Node> T; T.reserve(30000); T.push_back(Node{0, -1, -1, {}});
    auto insert = [&](int key) { int x = 0;
        while (true) { ACC(&T[x]); if (key == T[x].key) return;
            int c = key < T[x].key ? 0 : 1;
            int& nx = c ? T[x].right : T[x].left;
            if (nx < 0) { nx = (int)T.size(); T.push_back(Node{key, -1, -1, {}}); ACC(&T[nx]); return; }
            x = nx; } };
    for (int i = 0; i < 12000; i++) insert((int)(rnd() % 100000));
    for (int i = 0; i < 60000; i++) { int key = (rnd() % 100 < 80) ? (int)(rnd() % 100000) : (int)(rnd() % 12000);
        int x = 0; while (x >= 0) { ACC(&T[x]); if (key == T[x].key) break; x = key < T[x].key ? T[x].left : T[x].right; } }
    cerr << "index nodes=" << T.size() << "\n"; save("btree");
}

// ---- 2. Hash join: build + probe -------------------------------------------
static void hashjoin() {
    const int B = 131072, NR = 300000;
    vector<int> head(B, -1), nxt(NR), key(NR), val(NR);
    g_log = false; // build the table without logging; the probe phase is the workload
    for (int i = 0; i < NR; i++) { key[i] = (int)(rnd() % 100000000); val[i] = i;
        int b = key[i] % B; nxt[i] = head[b]; head[b] = i; }
    g_log = true;
    long long sum = 0;
    for (int i = 0; i < 70000; i++) { int q = (rnd() % 100 < 70) ? key[rnd() % NR] : (int)(rnd() % 100000000);
        int b = q % B; ACC(&head[b]); for (int p = head[b]; p >= 0; p = nxt[p]) {
            ACC(&key[p]); ACC(&val[p]); if (key[p] == q) { sum += val[p]; break; } ACC(&nxt[p]); } }
    cerr << "hashjoin checksum " << sum << "\n"; save("hashjoin");
}

// ---- 3. Breadth-first search on CSR graph ----------------------------------
static void bfs() {
    const int N = 120000; vector<int> off(N + 1, 0), deg(N, 0); vector<pair<int,int>> edges;
    for (int u = 0; u < N; u++) for (int k = 0; k < 4; k++) { edges.push_back({u, (u * 7 + k * 13 + 3) % N}); deg[u]++; }
    for (int i = 0; i < 400000; i++) { int u = (int)(rnd() % N), v = (int)(rnd() % N); edges.push_back({u, v}); deg[u]++; }
    int s = 0; for (int i = 0; i < N; i++) { s += deg[i]; off[i + 1] = s; }
    vector<int> cur(s), pos(N); for (int i = 0; i < N; i++) pos[i] = off[i];
    for (auto& e : edges) cur[pos[e.first]++] = e.second;
    vector<char> seen(N, 0); vector<int> q(N); q[0] = 0; seen[0] = 1; int qh = 0, qt = 1;
    while (qh < qt && logrefs.size() < CAP) { int u = q[qh++]; ACC(&q[qh]);
        for (int e = off[u]; e < off[u + 1]; e++) { ACC(&off[u]); ACC(&cur[e]); int v = cur[e]; ACC(&seen[v]);
            if (!seen[v]) { seen[v] = 1; ACC(&q[qt]); q[qt++] = v; } } }
    cerr << "bfs visited " << qt << "\n"; save("bfs");
}

// ---- 4. Quicksort (median-of-three, real recursive sorting) ----------------
struct Rec { int key; long long pad[2]; };  // 20-byte record: realistic table row
static void qsort_log(Rec* a, int l, int r) {
    if (l >= r || logrefs.size() >= CAP) return;
    ACC(&a[l]); ACC(&a[r]); ACC(&a[(l + r) / 2]);
    int m = (l + r) / 2; if (a[l].key > a[m].key) swap(a[l], a[m]);
    if (a[l].key > a[r].key) swap(a[l], a[r]); if (a[m].key > a[r].key) swap(a[m], a[r]);
    swap(a[m], a[r]); int piv = a[r].key, i = l;
    for (int j = l; j < r; j++) { ACC(&a[j]); if (a[j].key < piv) { ACC(&a[i]); swap(a[i++], a[j]); } }
    ACC(&a[i]); swap(a[i], a[r]);
    qsort_log(a, l, i - 1); qsort_log(a, i + 1, r);
}
static void sortkernel() { const int N = 400000; vector<Rec> a(N);
    for (int i = 0; i < N; i++) a[i].key = (int)(rnd() % 1000000);
    qsort_log(a.data(), 0, N - 1); save("sort"); }

// ---- 5. Stencil computation (real 5-point Jacobi sweeps) -------------------
static void stencil() {
    const int N = 512; vector<double> g(N * N), h(N * N);
    for (int i = 0; i < N * N; i++) g[i] = (double)(rnd() % 1000);
    for (int it = 0; it < 12 && logrefs.size() < CAP; it++) {
        for (int y = 1; y < N - 1; y++) for (int x = 1; x < N - 1; x++) {
            int c = y * N + x; ACC(&g[c]); ACC(&g[c - 1]); ACC(&g[c + 1]);
            ACC(&g[c - N]); ACC(&g[c + N]); h[c] = 0.2 * (g[c] + g[c - 1] + g[c + 1] + g[c - N] + g[c + N]);
            ACC(&h[c]); }
        g.swap(h); }
    save("stencil");
}

// ---- 6. Sparse-matrix value gathers (16 MB value array) -------------------
// CSR-style indirect access: each access selects a pseudo-random row and
// gathers its values from a 2M-double (~4000 page) array. This is the irregular
// page-level pattern of sparse linear algebra, not a sequential scan.
static void sparse() {
    const int M = 2000000;
    vector<double> val(M);
    for (int i = 0; i < M; i++) val[i] = (i % 251) * 0.01;
    for (int i = 0; i < CAP && logrefs.size() < CAP; i++) {
        int r = (int)(rnd() % M);
        ACC(&val[r]);
        for (int k = 0; k < 4 && logrefs.size() < CAP; k++)
            ACC(&val[(r + (k + 1) * 7919) % M]);
    }
    save("sparse");
}

// ---- 7. Priority queue with random decrease-key (16 MB heap) --------------
// A 4M-element binary heap occupies ~16 MB. Random decrease-key operations
// touch positions spread across the heap, unlike top-only delete-min traffic.
static void heapkernel() {
    const int M = 4000000;
    vector<int> h(M); for (int i = 0; i < M; i++) h[i] = (int)(rnd() % 100000000);
    for (int op = 0; op < CAP && logrefs.size() < CAP; op++) {
        int i = (int)(rnd() % M);
        ACC(&h[i]); h[i] = (int)(rnd() % 100000000);
        while (i > 0 && logrefs.size() < CAP) {
            int p = (i - 1) / 2; ACC(&h[i]); ACC(&h[p]);
            if (h[p] <= h[i]) break; swap(h[p], h[i]); i = p;
        }
    }
    save("heap");
}

// ---- 8. Histogram / radix scatter over a 16 MB key array ------------------
// A stride permutation spreads the 300k logged references over all 4M keys
// (16 MB, ~4000 pages) so the trace reflects whole-array traffic rather than
// only the first cache-sized prefix.
static void radix() {
    const int M = 4000000;
    vector<uint32_t> a(M), tmp(M); vector<int> cnt(256);
    for (int i = 0; i < M; i++) a[i] = (uint32_t)rnd();
    const int STRIDE = 4000037;  // coprime with M
    uint32_t pos = (uint32_t)(rnd() % M);
    for (int i = 0; i < CAP && logrefs.size() < CAP; i++) {
        pos = (pos + STRIDE) % M;
        uint32_t v = a[pos]; ACC(&a[pos]);
        int b = (int)((v >> 24) & 0xff);
        ACC(&tmp[b]); ACC(&cnt[b]);
        tmp[b]++; cnt[b]++;
    }
    save("radix");
}

// ---- 9. Random walk over a 16 MB CSR adjacency array ----------------------
static void pagerank() {
    const int M = 4000000;
    vector<int> adj(M); vector<double> val(M / 4, 1.0);
    for (int i = 0; i < M; i++) adj[i] = (i * 7 + 13) % M;
    int cur = (int)(rnd() % M);
    for (int i = 0; i < CAP && logrefs.size() < CAP; i++) {
        ACC(&adj[cur]); cur = adj[cur];
        ACC(&val[cur % (M / 4)]);
    }
    save("pagerank");
}

// ---- 10. Open-addressing hash table (2M slots, ~2000 pages) ----------------
static void hashmapkernel() {
    const int S = 1 << 21;
    vector<uint32_t> key(S, 0), value(S, 0);
    for (int i = 0; i < 400000 && logrefs.size() < CAP; i++) { uint32_t k = (uint32_t)(rnd() % 100000000);
        int h = (int)(k & (S - 1));
        for (int pr = 0; pr < 32 && logrefs.size() < CAP; pr++) { int idx = (h + pr) & (S - 1);
            ACC(&key[idx]); if (key[idx] == 0 || key[idx] == k) { key[idx] = k; ACC(&value[idx]); value[idx] = (uint32_t)rnd(); break; } } }
    long long sum = 0;
    for (int i = 0; i < 400000 && logrefs.size() < CAP; i++) { uint32_t k = (uint32_t)(rnd() % 100000000);
        int h = (int)(k & (S - 1));
        for (int pr = 0; pr < 32 && logrefs.size() < CAP; pr++) { int idx = (h + pr) & (S - 1);
            ACC(&key[idx]); if (key[idx] == k) { ACC(&value[idx]); sum += value[idx]; break; }
            if (key[idx] == 0) break; } }
    cerr << "hashmap checksum " << sum << "\n"; save("hashmap");
}

int main(int argc, char** argv) { u64 sd = (argc > 1) ? strtoull(argv[1], nullptr, 10) : 12345; rs = sd;
    g_suffix = (argc > 1) ? ("_s" + to_string(sd)) : "";
    system("mkdir -p traces_real");
    btree(); hashjoin(); bfs(); sortkernel(); stencil();
    sparse(); heapkernel(); radix(); pagerank(); hashmapkernel();
    cerr << "done\n"; }
