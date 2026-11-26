// Integrated D-1 + D0 cycle runner, accounting (slippage, costs, equity path) and performance metrics.
#pragma once
#include <map>
#include <string>
#include <utility>
#include <vector>
#include "d0_engine.hpp"
namespace a8 {
struct CycleTask { std::string und, expiry, d1, d0; int lot; };
struct CycleResult {
    std::string und, expiry, d1, d0; int lot = 0;
    double gross = 0, slippage = 0, costs = 0, net = 0, settle = 0; int n_orders = 0, n_fills = 0;
    bool d1_stopped = false, d0_stopped = false; int stop_minute = -1; bool handoff_error = false; int residual = 0; double min_path = 0, max_path = 0;
    std::vector<std::pair<double, double>> path;       // (epoch seconds, cumulative net P&L)
};
struct Waves { std::map<std::pair<std::string, std::string>, std::vector<std::pair<double, int>>> by_und_version; static Waves load(const std::string& csv); };
struct RunParams { double stop_rupees = 0.0; /* 0 = no stop */ double cost_mult = 1.0; double slip_mult = 1.0; };
CycleResult run_cycle(const CycleTask& t, const std::string& data_dir, const Waves& w, const RunParams& p);
std::vector<CycleTask> load_cycles(const std::string& csv);

struct Metrics { std::string label; int cycles = 0, weeks = 0; double net = 0, gross = 0, costs = 0, slippage = 0, cum_return_pct = 0, ann_return_pct = 0, vol_ann_pct = 0, sharpe = NaN, sortino = NaN, max_dd_rs = 0, max_dd_pct = 0, longest_dd_days = 0,
    win_rate_pct = 0, avg_win = 0, avg_loss = 0, profit_factor = NaN, expectancy = 0, median_cycle = 0, worst = 0, best = 0, cvar5 = 0, top5_share_pct = NaN, stop_rate_pct = 0; };
constexpr double CAPITAL_RS = 20000000.0;
Metrics compute_metrics(const std::vector<const CycleResult*>& v, const std::string& label);
std::string split_of(const std::string& d0);
std::string user_split(const std::string& d1, const std::string& d0);
}  // namespace a8
