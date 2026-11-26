// One trading session's market data: index one-minute bars and the full option chain on a 375-minute grid (09:15 .. 15:29).
#pragma once
#include <cstdint>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include "util.hpp"
namespace a8 {
enum Right { CE = 0, PE = 1 };
enum Field { OPEN = 0, HIGH = 1, LOW = 2, CLOSE = 3 };
struct Session {
    int nK = 0, n = 0;
    std::vector<double> K;                       // strikes, ascending
    std::vector<double> sp[4];                   // spot open/high/low/close [n]
    std::vector<double> opt[2][4];               // [right][field] -> nK * n, row-major (strike, minute); NaN where never traded before that minute
    std::unordered_map<long, int> kidx;
    double o(int r, int f, int ki, int j) const { return opt[r][f][(size_t)ki * n + j]; }
    int index_of(double strike) const { auto it = kidx.find((long)strike); return it == kidx.end() ? -1 : it->second; }
    // binary format A8S1: magic[4] int32 nK int32 n | float64 K[nK] | float64 spot[4][n] | float64 opt[2][4][nK*n]
    static Session load(const std::string& path) {
        FILE* f = std::fopen(path.c_str(), "rb"); if (!f) throw std::runtime_error("cannot open " + path);
        char mg[4]; int32_t a, b;
        if (std::fread(mg, 1, 4, f) != 4 || std::string(mg, 4) != "A8S1") { std::fclose(f); throw std::runtime_error("bad magic in " + path); }
        if (std::fread(&a, 4, 1, f) != 1 || std::fread(&b, 4, 1, f) != 1) { std::fclose(f); throw std::runtime_error("short header " + path); }
        Session s; s.nK = a; s.n = b; s.K.resize(a);
        auto rd = [&](std::vector<double>& v, size_t cnt) { v.resize(cnt); if (std::fread(v.data(), 8, cnt, f) != cnt) { std::fclose(f); throw std::runtime_error("short read " + path); } };
        rd(s.K, a); for (int i = 0; i < 4; ++i) rd(s.sp[i], b);
        for (int r = 0; r < 2; ++r) for (int i = 0; i < 4; ++i) rd(s.opt[r][i], (size_t)a * b);
        std::fclose(f); for (int i = 0; i < a; ++i) s.kidx[(long)s.K[i]] = i; return s;
    }
};
}  // namespace a8
