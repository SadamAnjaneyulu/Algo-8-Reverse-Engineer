// D0 (expiry-day) engine: timetable waves, breakout pairs, solo ladder with counter-sells, body buy-backs (stop / take-profit), opening wings,
// hedge controller, cycle hard stop, 15:14 clearance. Minute-resolution. Port of d0_strategy/d0_algo (Python reference).
#pragma once
#include <array>
#include <cmath>
#include <map>
#include <string>
#include <vector>
#include "d1_engine.hpp"
namespace a8 {
struct D0Config {
    std::vector<std::pair<double, int>> waves;      // (second of day, lots) per wave
    double buyback_theta = 1.4, buyback_tp = 0.1;   // stop: minute high >= theta x entry; take-profit: minute low <= tp x entry
    double ladder_step = 0.05; int ladder_gate_min = 60; bool ladder_mult = true; double counter_ratio = 0.25; int opening_wing_lots = 20;
    double cycle_stop_rupees = 1e18;
    int clearance_minute = 359, breakout_start_min = 75, breakout_end_min = 360, solo_lot_cap = 10, last_minute = 374;
    double wing_premium_frac = 0.025, opening_wing_offset_steps = 17.0;
    int max_short_lots_per_right = 306, max_sell_decisions_per_minute = 90;
};
enum Cls { C_BODY_SELL, C_BODY_BUYBACK, C_BODY_LONG, C_WING_BUY, C_WING_SELL, C_STOP };
struct Event { Cls cls; int cp; int j; long strike; int lots; std::vector<std::pair<int, int>> parts; /* stop: (kind 0 body_short,1 long,2 oshort ; lots) */ int side; /* +1 buy, -1 sell, 0 mixed */ double px; };
struct Opening { std::vector<std::array<double, 3>> lots; /* cp,strike,entry */ std::vector<std::array<long, 4>> longs; /* module(0 num,1 h_,2 v_), cp, strike, n */ double cash = 0.0; };
struct D0Result { std::vector<Event> events; bool stopped = false, cleared = false; int rejected = 0; int max_short_seen = 0; };

class D0Engine {
public:
    D0Engine(const D0Config& c, const Session& s, double unit, double step, const Opening& op);
    D0Result run();
private:
    D0Config cfg; const Session& S; double unit, step; std::vector<std::array<double, 3>> lots; std::vector<std::array<long, 4>> longs; double cash;
    std::vector<Event> events; bool stopped = false, cleared = false; int rejected = 0, max_short_seen = 0; std::map<int, int> decisions;
    std::map<int, std::vector<int>> fires, wave_by_minute; bool ref_has = false; double ref[2] = {0, 0}; double acc[2] = {0, 0};
    double px(int cp, double k, int j, int f = CLOSE) const;
    double atm(double x) const { int bi = 0; double bd = std::fabs(S.K[0] - x); for (int i = 1; i < S.nK; ++i) { double d = std::fabs(S.K[i] - x); if (d < bd) { bd = d; bi = i; } } return S.K[bi]; }
    void breakout_fires();
    void rec(Cls c, int cp, int j, double k, int n, int side, double p, const std::vector<std::pair<int, int>>& parts = {});
    int shorts_on(int cp) const { int n = 0; for (auto& l : lots) if ((int)l[0] == cp) ++n; return n; }
    bool risk_blocks(int cp, int n, int j);
    double mtm(int j) const;
    void cycle_stop(int j); void clearance(int j); std::array<int, 2> buybacks(int j);
    struct Sell { int cp; double k; int n; bool pair; };
    std::vector<Sell> sells(int j, double c0, double stp, const std::array<int, 2>& nbb);
    void opening_wings(double c0); void hedge(int j, int jp, double c0);
};
}  // namespace a8
