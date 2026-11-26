// algo8_backtest: runs the integrated D-1 + D0 algo over a list of weekly cycles and prints/writes the performance metrics.
#include <atomic>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <thread>
#include "algo8/backtest.hpp"
using namespace a8;
static void print_row(FILE* f, const Metrics& m) {
    std::fprintf(f, "%s,%d,%.2f,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.2f,%.4f,%.4f,%.2f,%.2f,%.2f,%.2f,%.2f,%.4f,%.4f,%.4f,%.4f\n", m.label.c_str(), m.cycles, m.net, m.gross, m.costs, m.slippage, m.win_rate_pct, m.sharpe, m.sortino, m.max_dd_rs, m.max_dd_pct, m.profit_factor, m.avg_win, m.avg_loss, m.worst, m.best, m.cvar5, m.ann_return_pct, m.vol_ann_pct, m.longest_dd_days, m.stop_rate_pct);
}
int main(int argc, char** argv) {
    std::string cycles, data, waves, out = "out"; RunParams P; P.stop_rupees = 200000.0; int threads = 4;
    for (int i = 1; i < argc; ++i) { std::string a = argv[i]; auto nx = [&]() -> std::string { if (i + 1 >= argc) { std::fprintf(stderr, "missing value for %s\n", a.c_str()); std::exit(2); } return argv[++i]; };
        if (a == "--cycles") cycles = nx(); else if (a == "--data") data = nx(); else if (a == "--waves") waves = nx(); else if (a == "--out") out = nx(); else if (a == "--stop") P.stop_rupees = std::stod(nx()); else if (a == "--cost-mult") P.cost_mult = std::stod(nx()); else if (a == "--slip-mult") P.slip_mult = std::stod(nx()); else if (a == "--threads") threads = std::stoi(nx());
        else { std::fprintf(stderr, "usage: algo8_backtest --cycles cycles.csv --data DIR --waves frozen_d0_waves.csv [--stop RUPEES (0 = none, default 200000)] [--cost-mult X] [--slip-mult X] [--threads N] [--out DIR]\n"); return 2; } }
    if (cycles.empty() || data.empty() || waves.empty()) { std::fprintf(stderr, "need --cycles, --data and --waves\n"); return 2; }
    auto tasks = load_cycles(cycles); Waves W = Waves::load(waves); std::vector<CycleResult> R(tasks.size()); std::atomic<size_t> next{0}; std::vector<std::thread> th;
    for (int w = 0; w < threads; ++w) th.emplace_back([&]() { for (;;) { size_t i = next++; if (i >= tasks.size()) break; try { R[i] = run_cycle(tasks[i], data, W, P); } catch (std::exception& e) { std::fprintf(stderr, "cycle %s %s failed: %s\n", tasks[i].und.c_str(), tasks[i].expiry.c_str(), e.what()); R[i].und = tasks[i].und; R[i].expiry = tasks[i].expiry; R[i].d1 = tasks[i].d1; R[i].d0 = tasks[i].d0; R[i].net = NaN; } } });
    for (auto& t : th) t.join();
    std::string mk = "mkdir -p " + out; if (std::system(mk.c_str()) != 0) return 3;
    std::ofstream L(out + "/ledger.csv"); L.precision(10); L << "und,expiry,d1,d0,lot,gross,slippage,costs,net,n_orders,n_fills,d1_stopped,d0_stopped,stop_minute,handoff_error,residual,min_path,max_path,split\n";
    for (auto& r : R) L << r.und << ',' << r.expiry << ',' << r.d1 << ',' << r.d0 << ',' << r.lot << ',' << r.gross << ',' << r.slippage << ',' << r.costs << ',' << r.net << ',' << r.n_orders << ',' << r.n_fills << ',' << r.d1_stopped << ',' << r.d0_stopped << ',' << r.stop_minute << ',' << r.handoff_error << ',' << r.residual << ',' << r.min_path << ',' << r.max_path << ',' << split_of(r.d0) << '\n';
    FILE* M = std::fopen((out + "/metrics.csv").c_str(), "w"); std::fprintf(M, "label,cycles,net_pnl,gross_pnl,costs,slippage,win_rate_pct,sharpe,sortino,max_dd_rs,max_dd_pct,profit_factor,avg_win,avg_loss,worst_cycle,best_cycle,cvar5_cycle,ann_return_pct,vol_ann_pct,longest_dd_days,stop_rate_pct\n");
    for (std::string sc : {"ALL", "NIFTY", "SENSEX"}) for (std::string sp : {"ALL_PERIODS", "PRE", "DEV", "POST", "USER_IS", "USER_OOS"}) {
        std::vector<const CycleResult*> v; for (auto& r : R) { if (r.net != r.net) continue; if (sc != "ALL" && r.und != sc) continue; bool in = sp == "ALL_PERIODS" || split_of(r.d0) == sp || user_split(r.d1, r.d0) == sp; if (in) v.push_back(&r); }
        if (v.empty()) continue; Metrics m = compute_metrics(v, sc + "|" + sp); print_row(M, m);
        if (sp == "ALL_PERIODS" || sp == "PRE" || sp == "DEV" || sp == "POST") std::printf("%-22s cycles %3d  net %12.0f  win %5.1f%%  Sharpe %6.2f  maxDD %11.0f (%5.2f%%)  PF %5.2f  worst %11.0f\n", m.label.c_str(), m.cycles, m.net, m.win_rate_pct, m.sharpe, m.max_dd_rs, m.max_dd_pct, m.profit_factor, m.worst);
    }
    std::fclose(M); std::printf("wrote %s/ledger.csv and %s/metrics.csv\n", out.c_str(), out.c_str()); return 0;
}
