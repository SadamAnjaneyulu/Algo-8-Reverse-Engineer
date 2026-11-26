// Debug/parity helper: prints the D-1 fills and the D0 events of one cycle (same text format as tools/dump_cycle.py).
#include <cstdio>
#include "algo8/backtest.hpp"
using namespace a8;
int main(int argc, char** argv) {
    if (argc < 8) { std::fprintf(stderr, "usage: dump_cycle DATA WAVES UND EXPIRY D1 D0 LOT [STOP]\n"); return 2; }
    std::string dir = argv[1]; Waves W = Waves::load(argv[2]); std::string und = argv[3], ex = argv[4], d1 = argv[5], d0 = argv[6]; int lot = std::stoi(argv[7]); double stop = argc > 8 ? std::stod(argv[8]) : 0.0;
    Session s1 = Session::load(dir + "/" + und + "_" + ex + "_" + d1 + ".a8s"), s0 = Session::load(dir + "/" + und + "_" + ex + "_" + d0 + ".a8s");
    D1Config c1 = d1_config_for(und, d1, lot, stop > 0, stop); D1Engine e1(c1, s1); D1Result r1 = e1.run();
    for (auto& f : r1.fills) std::printf("D1 %.0f %d %.0f %d %d %.2f %d\n", f.ts, f.right, f.strike, f.side, f.lots, f.price, (int)f.role);
    if (r1.stopped) { std::printf("D1STOP %.0f\n", r1.stop_time); return 0; }
    Opening op; std::vector<const Book::SK*> keys; for (auto& s : r1.book.shorts) keys.push_back(&s); std::sort(keys.begin(), keys.end(), [](const Book::SK* a, const Book::SK* b) { return a->r != b->r ? a->r < b->r : a->k < b->k; });
    for (auto* s : keys) for (auto& l : s->lots) op.lots.push_back({(double)s->r, (double)s->k, l.entry});
    auto wl = r1.book.wings; std::sort(wl.begin(), wl.end()); for (auto& w : wl) if (w[2] > 0) op.longs.push_back({1, w[0], w[1], w[2]});
    auto lp = r1.book.lump; std::sort(lp.begin(), lp.end()); for (auto& w : lp) if (w[2] > 0) op.longs.push_back({2, w[0], w[1], w[2]});
    double cash = 0; for (auto& f : r1.fills) cash += (f.side < 0 ? 1.0 : -1.0) * f.price * f.lots * (double)lot; op.cash = cash;
    std::printf("OPEN lots %zu longs %zu cash %.6f\n", op.lots.size(), op.longs.size(), cash);
    D0Config c0; std::string ver = d1 >= "2026-09-16" ? "V2" : "V1"; auto it = W.by_und_version.find({und, ver}); if (it != W.by_und_version.end()) c0.waves = it->second; c0.cycle_stop_rupees = stop > 0 ? stop : 1e18;
    D0Engine e0(c0, s0, (double)lot, und == "NIFTY" ? 50.0 : 100.0, op); D0Result r0 = e0.run();
    for (auto& e : r0.events) std::printf("D0 %d %d %ld %d %d %.4f\n", (int)e.cls, e.cp, e.strike, e.j, e.lots, e.px);
    return 0;
}
