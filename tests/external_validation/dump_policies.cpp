// tests/external_validation/dump_policies.cpp
// Standalone driver calling mkPolicy() from src/pathA_sim.cpp for external cross-validation.
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

#define main pathA_sim_main
#include "../../src/pathA_sim.cpp"
#undef main

int main(int argc, char** argv) {
    if (argc < 4) {
        fprintf(stderr, "Usage: %s <trace.bin> <C> <policy1,policy2,...>\n", argv[0]);
        return 1;
    }
    string tracePath = argv[1];
    int C = atoi(argv[2]);
    string polList = argv[3];

    ifstream in(tracePath, ios::binary);
    if (!in) { fprintf(stderr, "cannot open %s\n", tracePath.c_str()); return 1; }
    in.seekg(0, ios::end);
    size_t bytes = (size_t)in.tellg();
    in.seekg(0, ios::beg);
    vector<u32> refs(bytes / sizeof(u32));
    in.read((char*)refs.data(), (streamsize)(refs.size() * sizeof(u32)));

    u32 maxPage = *max_element(refs.begin(), refs.end());
    NP = (int)min<u64>((u64)maxPage + 1, 1ULL << 28);

    size_t warm = min<size_t>(100000, refs.size() / 10);
    size_t nEval = refs.size() - warm;

    stringstream ss(polList);
    string pname;
    while (getline(ss, pname, ',')) {
        auto pol = mkPolicy(pname, C);
        size_t totalMiss = 0, evalMiss = 0;
        for (size_t i = 0; i < refs.size(); i++) {
            bool hit = pol->access(refs[i]);
            if (!hit) {
                totalMiss++;
                if (i >= warm) evalMiss++;
            }
        }
        printf("%s,%d,%zu,%zu,%zu,%zu,%.9f\n",
               pname.c_str(), C, refs.size(), warm, totalMiss, evalMiss,
               (double)evalMiss / (double)nEval);
    }
    return 0;
}
