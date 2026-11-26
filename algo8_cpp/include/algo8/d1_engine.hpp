// D-1 engine: scheduled straddles, two-candle breakout pairs, solo ladder, per-lot stops, wing controller, overnight lump, cycle hard stop.
// Port of d1_strategy/d1_algo (Python reference); driven second by second over a replayed session (paper broker, fills at the replay price).
#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <set>
#include <unordered_map>
#include <vector>
#include "session.hpp"
namespace a8 {
constexpr int OPEN_S = 33300;                         // 09:15:00
enum Role { R_SCHED, R_BRK, R_BRKX, R_LADDER, R_STOP, R_WBUY, R_WSELL, R_OWING, R_LUMP, R_CSBUY, R_CSSELL };
inline bool is_sell_role(Role r) { return r <= R_LADDER; }
inline bool is_reducing(Role r) { return r == R_STOP || r == R_CSBUY || r == R_CSSELL || r == R_WBUY || r == R_OWING || r == R_LUMP; }

struct D1Config {
    std::string und = "NIFTY"; double strike_step = 50.0; int lot_units = 65; int freeze_lots = 27; double price_tick = 0.05;
    std::vector<int> timetable; double max_wave_lateness_s = 30.0;
    int breakout_start_min = 75, breakout_end_min = 360; double pairs_per_depth_step = 0.4; int max_pairs = 3; double extra_a = 0.81, extra_b = 1.28; int max_extra = 7;
    double ladder_step = 0.2; int ladder_gate_min = 60; int ladder_strike_window = 4; double stop_ratio = 1.6;
    double wing_premium_frac = 0.025, wing_delay_s = 4.0; int opening_wing_lots_per_right = 3; double opening_wing_offset_steps = 39.8;
    int lump_minute = 356; double lump_ratio = 0.827, lump_sigma_mult = 2.2; double limit_buffer_pct = 15.0;
    int max_short_lots_per_right = 400, max_orders_per_minute = 40; bool one_lot_v2 = true;
    bool has_stop = false; double cycle_stop_rupees = 0.0; int cycle_stop_check_s = 5;
    double lump_time_s() const { return OPEN_S + 60.0 * lump_minute; }
};
D1Config d1_config_for(const std::string& und, const std::string& d1_date, int lot_units, bool has_stop, double stop_rupees);

struct Lot { double ts; int minute; double entry; Role role; };
struct Fill { double ts; int right; double strike; int lots; int side; double price; Role role; };   // side: +1 buy, -1 sell
struct Req { int tag; double ts; int right; double strike; int lots; int side; double limit; Role role; int did; };

struct SpotBars {
    std::vector<double> open, high, low, close; int minute = -1; double co = NaN, ch = NaN, cl = NaN, cc = NaN;
    void tick(int m, double p) {
        if (m != minute) {
            if (minute >= 0) {
                open.push_back(co); high.push_back(ch); low.push_back(cl); close.push_back(cc);
                for (int i = 0; i < m - minute - 1; ++i) { open.push_back(cc); high.push_back(cc); low.push_back(cc); close.push_back(cc); }
            }
            minute = m; co = ch = cl = cc = p;
        } else { ch = std::max(ch, p); cl = std::min(cl, p); cc = p; }
    }
    bool prev_close(int m, double& out) const { if (0 < m && m <= (int)close.size()) { out = close[m - 1]; return true; } return false; }
    int completed() const { return (int)close.size(); }
};

struct Book {
    struct SK { int r; long k; std::vector<Lot> lots; };
    std::vector<SK> shorts; std::unordered_map<long, int> sidx;
    std::vector<std::array<long, 3>> wings, lump;            // {right, strike, lots} insertion order
    std::unordered_map<long, int> widx, lidx;
    int pending_short[2] = {0, 0}, pending_wing[2] = {0, 0};
    static long key(int r, long k) { return (long)r * 1000000000L + k; }
    int short_count(int r, bool pend) const { int n = 0; for (auto& s : shorts) if (s.r == r) n += (int)s.lots.size(); return n + (pend ? pending_short[r] : 0); }
    int wing_count(int r, bool pend) const { int n = 0; for (auto& w : wings) if (w[0] == r && w[2] > 0) n += (int)w[2]; return n + (pend ? pending_wing[r] : 0); }
    SK& sk(int r, long k) { auto it = sidx.find(key(r, k)); if (it != sidx.end()) return shorts[it->second]; sidx[key(r, k)] = (int)shorts.size(); shorts.push_back({r, k, {}}); return shorts.back(); }
    void add_short(int r, long k, const Lot& l, int n) { auto& s = sk(r, k); for (int i = 0; i < n; ++i) s.lots.push_back(l); }
    int remove_shorts(int r, long k, int n) {            // cheapest entry first (stable)
        auto& s = sk(r, k); std::vector<Lot> v = s.lots; std::stable_sort(v.begin(), v.end(), [](const Lot& a, const Lot& b) { return a.entry < b.entry; });
        int kk = std::min(n, (int)v.size()); s.lots.assign(v.begin() + kk, v.end()); return kk; }
    static long& slot(std::vector<std::array<long, 3>>& v, std::unordered_map<long, int>& idx, int r, long k) { auto it = idx.find(key(r, k)); if (it != idx.end()) return v[it->second][2]; idx[key(r, k)] = (int)v.size(); v.push_back({r, k, 0}); return v.back()[2]; }
    void add_wing(int r, long k, int n) { slot(wings, widx, r, k) += n; }
    void sell_wing(int r, long k, int n) { long& v = slot(wings, widx, r, k); v = std::max<long>(v - n, 0); }
    long wing_of(int r, long k) { auto it = widx.find(key(r, k)); return it == widx.end() ? 0 : wings[it->second][2]; }
    void add_lump(int r, long k, int n) { slot(lump, lidx, r, k) += n; }
    void sub_lump(int r, long k, long n) { long& v = slot(lump, lidx, r, k); v = std::max<long>(v - n, 0); }
};

struct D1Result { std::vector<Fill> fills; int orders = 0, rejected = 0; bool stopped = false; double stop_time = NaN; Book book; };

class D1Engine {
public:
    D1Engine(const D1Config& c, const Session& s) : cfg(c), S(s), n(s.n) { }
    D1Result run();                                      // replay the whole session, second by second
private:
    D1Config cfg; const Session& S; int n; double t = 0.0;
    SpotBars bars; Book book; std::vector<Fill> fills; int orders_n = 0, rejected_n = 0, seq = 0, decision_seq = 0;
    std::unordered_map<int, std::pair<Req, int>> pending; std::map<std::pair<int, long>, int> pending_stop;
    std::set<int> done_waves; bool done_opening = false, done_lump = false; std::set<std::pair<int, int>> breaks_done;
    struct PB { double t0, ext; }; std::map<std::pair<int, int>, PB> pending_breaks; std::map<int, std::pair<double, double>> channels;
    bool ref_has[2] = {false, false}; double ladder_ref[2] = {0, 0}; int ladder_from[2] = {1000000000, 1000000000};
    bool last_has[2] = {false, false}; double last_sale[2] = {0, 0};
    bool wing_has = false; double wing_first = 0, wing_last = 0;
    bool stopped = false; double stop_time = NaN, next_stop_check = 0.0;
    std::map<int, int> minute_counts; std::map<int, std::set<int>> minute_decisions;
    // option minute bars from LTP samples: [contract][minute] -> o,h,l,c
    std::unordered_map<long, std::vector<std::array<double, 4>>> obars; std::unordered_map<long, std::vector<char>> ohas;
    // ---- feed (replay path through each one-minute bar)
    void pos(int& j, int& s) const { int tt = (int)(t - OPEN_S); j = (int)std::floor((double)tt / 60.0); s = tt - 60 * j; }
    double spot() const;
    double option_ltp(int r, double strike) const;
    // ---- helpers
    double atm(double price) const { int bi = 0; double bd = std::fabs(S.K[0] - price); for (int i = 1; i < S.nK; ++i) { double d = std::fabs(S.K[i] - price); if (d < bd) { bd = d; bi = i; } } return S.K[bi]; }
    double tick_round(double x, bool up) const { double tk = cfg.price_tick; return (up ? std::ceil(x / tk - 1e-9) : std::floor(x / tk + 1e-9)) * tk; }
    void sample_options(int j, double sp);
    void obar_sample(int r, double strike, int j, double p);
    double obar_run_high(int r, double strike, int j) const; double obar_prev_close(int r, double strike, int j) const;
    bool submit(int r, double strike, int lots, int side, Role role);
    bool risk_check(const Req& q, int short_count, int minute);
    void pending_adjust(const Req& q, int nn, int sign);
    void process_fill(const Fill& f);
    void note_body(double tt) { if (!wing_has) wing_first = tt; wing_has = true; wing_last = tt; }
    double book_mtm() const;
    void cycle_stop(); void opening_wings(int j); void scheduled(int j); void breakout(int j, double sp); void fire_breakout(int j, int side, double depth);
    void ladder_event(int r, int j); bool solo_strike(int r, int j, double& k); void ladder(int j); void stops(int j); void wing_controller(int j); void lump(int j);
    bool channel(int b0, double& top, double& bottom);
    void step();
};
}  // namespace a8
