#include "algo8/d1_engine.hpp"
namespace a8 {
static const int SCHED_A[33] = {1, 2, 7, 900, 900, 1800, 1831, 1866, 2710, 3599, 3600, 3600, 3658, 4510, 5431, 5491, 6300, 6310, 7199, 7258, 8110, 9000, 9031, 9091, 9910, 11700, 11710, 14400, 15240, 16140, 17040, 17940, 18840};
static const int SCHED_B[33] = {1, 2, 8, 899, 900, 1800, 1831, 1866, 2710, 3599, 3600, 3658, 4501, 4510, 5431, 5491, 6310, 7199, 7258, 8102, 8110, 9031, 9091, 9910, 11702, 11710, 15302, 16140, 17040, 17940, 18840, 18902, 19740};
D1Config d1_config_for(const std::string& und, const std::string& d1, int lot_units, bool has_stop, double stop_rupees) {
    D1Config c; bool nifty = und == "NIFTY"; c.und = und; c.strike_step = nifty ? 50.0 : 100.0; c.lot_units = lot_units; c.freeze_lots = nifty ? 27 : 50; c.lump_ratio = nifty ? 0.827 : 0.503;
    bool vb = d1 >= "2026-09-16"; c.timetable.assign(vb ? SCHED_B : SCHED_A, (vb ? SCHED_B : SCHED_A) + 33);
    c.opening_wing_offset_steps = (!nifty && vb) ? 20.0 : 39.8;
    c.lump_minute = d1 <= "2026-08-05" ? 356 : (d1 <= "2026-08-19" ? 368 : 375);
    c.has_stop = has_stop; c.cycle_stop_rupees = stop_rupees; return c;
}
// ---------------------------------------------------------------- feed
double D1Engine::spot() const {
    int j, s; pos(j, s); if (j < 0) return NaN; if (j >= n) return S.sp[CLOSE][n - 1];
    bool up = S.sp[CLOSE][j] >= S.sp[OPEN][j]; double o = S.sp[OPEN][j], h = S.sp[HIGH][j], l = S.sp[LOW][j], c = S.sp[CLOSE][j];
    double nodes[4] = {o, up ? l : h, up ? h : l, c}; return interp4((double)s, nodes);
}
double D1Engine::option_ltp(int r, double strike) const {
    int i = S.index_of((double)(long)strike); if (i < 0) return NaN; int j, s; pos(j, s); if (j < 0) return NaN;
    int jj = j < n ? std::min(j, n - 1) : n - 1; double o = S.o(r, OPEN, i, jj), h = S.o(r, HIGH, i, jj), l = S.o(r, LOW, i, jj), c = S.o(r, CLOSE, i, jj);
    if (j >= n) return c;
    bool sup = S.sp[CLOSE][jj] >= S.sp[OPEN][jj]; bool low_first = (r == CE) ? sup : !sup;
    double nodes[4] = {o, low_first ? l : h, low_first ? h : l, c}; return interp4((double)s, nodes);
}
// ---------------------------------------------------------------- option bars
void D1Engine::obar_sample(int r, double strike, int j, double p) {
    if (isnan_(p)) return; long k = Book::key(r, (long)strike); auto& v = obars[k]; auto& h = ohas[k]; if (v.empty()) { v.resize(400); h.assign(400, 0); }
    if (!h[j]) { v[j] = {p, p, p, p}; h[j] = 1; } else { v[j][1] = std::max(v[j][1], p); v[j][2] = std::min(v[j][2], p); v[j][3] = p; }
}
double D1Engine::obar_run_high(int r, double strike, int j) const { auto it = ohas.find(Book::key(r, (long)strike)); if (it == ohas.end() || !it->second[j]) return NaN; return obars.at(it->first)[j][1]; }
double D1Engine::obar_prev_close(int r, double strike, int j) const { if (j - 1 < 0) return NaN; auto it = ohas.find(Book::key(r, (long)strike)); if (it == ohas.end() || !it->second[j - 1]) return NaN; return obars.at(it->first)[j - 1][3]; }
void D1Engine::sample_options(int j, double sp) {
    double a0 = atm(sp), w = (cfg.ladder_strike_window + 1) * cfg.strike_step;
    for (int r = 0; r < 2; ++r) for (int i = 0; i < S.nK; ++i) if (std::fabs(S.K[i] - a0) <= w) obar_sample(r, S.K[i], j, option_ltp(r, S.K[i]));
    for (auto& s : book.shorts) if (!s.lots.empty()) obar_sample(s.r, (double)s.k, j, option_ltp(s.r, (double)s.k));
}
// ---------------------------------------------------------------- order plumbing
bool D1Engine::risk_check(const Req& q, int short_count, int minute) {
    if (q.lots <= 0) return false; if (!(q.limit == q.limit && q.limit > 0)) return false;
    int cnt = minute_counts.count(minute) ? minute_counts[minute] : 0; bool shared = cfg.one_lot_v2 && minute_decisions[minute].count(q.did);
    if (cnt >= cfg.max_orders_per_minute && !shared) return false;
    bool adds = !is_reducing(q.role) && q.role != R_WSELL && q.side < 0;
    if (adds && short_count + q.lots > cfg.max_short_lots_per_right) return false;
    if (!shared) { minute_counts[minute] = cnt + 1; if (cfg.one_lot_v2) minute_decisions[minute].insert(q.did); }
    return true;
}
void D1Engine::pending_adjust(const Req& q, int nn, int sign) {
    if (q.role == R_CSBUY || q.role == R_CSSELL) return;
    if (is_sell_role(q.role)) book.pending_short[q.right] += sign * nn;
    else if (q.role == R_STOP) { book.pending_short[q.right] -= sign * nn; pending_stop[{q.right, (long)q.strike}] += sign * nn; }
    else if (q.role == R_WBUY || q.role == R_OWING) book.pending_wing[q.right] += sign * nn;
    else if (q.role == R_WSELL) book.pending_wing[q.right] -= sign * nn;
}
void D1Engine::process_fill(const Fill& f) {
    // pending bookkeeping is keyed by tag in the Python reference; fills carry their request here
    fills.push_back(f); int minute = (int)std::floor((f.ts - OPEN_S) / 60.0); long k = (long)f.strike;
    if (is_sell_role(f.role) && f.side < 0) { book.add_short(f.right, k, Lot{f.ts, minute, f.price, f.role}, f.lots); last_has[f.right] = true; last_sale[f.right] = f.price; }
    else if (f.role == R_STOP || f.role == R_CSBUY) book.remove_shorts(f.right, k, f.lots);
    else if (f.role == R_CSSELL) { long w = std::min<long>(book.wing_of(f.right, k), f.lots); book.sell_wing(f.right, k, (int)w); if (f.lots - w > 0) book.sub_lump(f.right, k, f.lots - w); }
    else if (f.role == R_WBUY || f.role == R_OWING) book.add_wing(f.right, k, f.lots);
    else if (f.role == R_WSELL) book.sell_wing(f.right, k, f.lots);
    else if (f.role == R_LUMP) book.add_lump(f.right, k, f.lots);
}
bool D1Engine::submit(int r, double strike, int lots, int side, Role role) {
    int j = (int)std::floor((t - OPEN_S) / 60.0); double ltp = option_ltp(r, strike); if (isnan_(ltp) || ltp <= 0) return false;
    int left = lots; bool ok_any = false; bool one_lot = cfg.one_lot_v2 && (role == R_OWING || role == R_STOP); ++decision_seq; int did = decision_seq;
    while (left > 0) {
        int nn = one_lot ? 1 : std::min(left, cfg.freeze_lots); left -= nn;
        double limit = side > 0 ? tick_round(ltp * (1.0 + cfg.limit_buffer_pct / 100.0), true) : tick_round(ltp * (1.0 - cfg.limit_buffer_pct / 100.0), false); limit = std::max(limit, cfg.price_tick);
        ++seq; Req q{seq, t, r, strike, nn, side, limit, role, did};
        if (!risk_check(q, book.short_count(r, true), j)) { ++rejected_n; continue; }
        ++orders_n; pending[q.tag] = {q, nn}; pending_adjust(q, nn, +1); ok_any = true;
        // paper broker: marketable orders fill at the replay price (limit checked), rounded to the paisa
        double lt = option_ltp(r, strike);
        if (isnan_(lt) || lt <= 0) continue;
        double px; if (side > 0) { if (q.limit < lt) continue; px = lt * (1.0 + 0.0); } else { if (q.limit > lt) continue; px = lt * (1.0 - 0.0); }
        Fill f{t, r, strike, nn, side, py_round2(px), role};
        auto it = pending.find(q.tag); if (it != pending.end()) { pending_adjust(q, f.lots, -1); it->second.second -= f.lots; if (it->second.second <= 0) pending.erase(it); }
        process_fill(f);
    }
    return ok_any;
}
// ---------------------------------------------------------------- book MTM and cycle stop
double D1Engine::book_mtm() const {
    double u = cfg.lot_units, v = 0.0;
    for (auto& f : fills) v += (f.side < 0 ? 1.0 : -1.0) * f.price * f.lots * u;
    for (auto& s : book.shorts) if (!s.lots.empty()) { double p = option_ltp(s.r, (double)s.k); if (!isnan_(p)) v -= p * (double)s.lots.size() * u; }
    for (int d = 0; d < 2; ++d) for (auto& w : (d == 0 ? book.wings : book.lump)) if (w[2] > 0) { double p = option_ltp((int)w[0], (double)w[1]); if (!isnan_(p)) v += p * (double)w[2] * u; }
    return v;
}
void D1Engine::cycle_stop() {
    std::vector<std::array<long, 3>> sh; for (auto& s : book.shorts) if (!s.lots.empty()) sh.push_back({s.r, s.k, (long)s.lots.size()}); std::sort(sh.begin(), sh.end());
    for (auto& e : sh) submit((int)e[0], (double)e[1], (int)e[2], +1, R_CSBUY);
    for (int d = 0; d < 2; ++d) { auto v = d == 0 ? book.wings : book.lump; std::sort(v.begin(), v.end()); for (auto& e : v) if (e[2] > 0) submit((int)e[0], (double)e[1], (int)e[2], -1, R_CSSELL); }
    stopped = true; stop_time = t;
}
// ---------------------------------------------------------------- rules
void D1Engine::opening_wings(int j) {
    if (done_opening || t < OPEN_S + 60 || j > 3) return; double pc; if (!bars.prev_close(j, pc)) return;
    for (int r = 0; r < 2; ++r) { int sg = r == CE ? 1 : -1; double k = atm(atm(pc) + sg * cfg.opening_wing_offset_steps * cfg.strike_step); submit(r, k, cfg.opening_wing_lots_per_right, +1, R_OWING); }
    done_opening = true; note_body(t);
}
void D1Engine::ladder_event(int r, int j) { double pc; if (bars.prev_close(j, pc)) { ref_has[r] = true; ladder_ref[r] = pc; ladder_from[r] = j + 1; } }
void D1Engine::scheduled(int j) {
    for (int w = 0; w < (int)cfg.timetable.size(); ++w) {
        if (done_waves.count(w)) continue; double target = OPEN_S + 60 + cfg.timetable[w]; if (t < target) continue; done_waves.insert(w);
        if (t - target > cfg.max_wave_lateness_s) continue; double pc; if (!bars.prev_close(j, pc)) continue; double k = atm(pc);
        for (int r = 0; r < 2; ++r) { submit(r, k, 1, -1, R_SCHED); ladder_event(r, j); } note_body(t);
    }
}
bool D1Engine::channel(int b0, double& top, double& bottom) {
    auto it = channels.find(b0); if (it != channels.end()) { top = it->second.first; bottom = it->second.second; return true; }
    int a = (int)std::ceil((double)(b0 - 3600 - OPEN_S) / 60.0), e = (int)std::ceil((double)(b0 - OPEN_S) / 60.0);
    if (e - std::max(a, 0) < 2 || bars.completed() < e) return false;
    int aa = std::max(a, 0); int hi = std::min(e, bars.completed()); if (aa >= hi) return false;
    double H = bars.high[aa], L = bars.low[aa]; for (int i = aa + 1; i < hi; ++i) { H = std::max(H, bars.high[i]); L = std::min(L, bars.low[i]); }
    channels[b0] = {H, L}; top = H; bottom = L; return true;
}
void D1Engine::breakout(int j, double sp) {
    if (!(cfg.breakout_start_min <= j && j <= cfg.breakout_end_min)) return;
    int b0 = ((OPEN_S + 60 * j) / 1800) * 1800; double top, bottom; if (!channel(b0, top, bottom)) return;
    for (int side : {1, -1}) {
        bool broke = side == 1 ? sp > top : sp < bottom; auto key = std::make_pair(b0, side); if (breaks_done.count(key)) continue;
        auto it = pending_breaks.find(key); if (it == pending_breaks.end()) { if (!broke) continue; it = pending_breaks.emplace(key, PB{t, sp}).first; }
        it->second.ext = side > 0 ? std::max(it->second.ext, sp) : std::min(it->second.ext, sp);
        if (t - it->second.t0 >= 0.0) { double depth = side > 0 ? (it->second.ext - top) / cfg.strike_step : (bottom - it->second.ext) / cfg.strike_step; fire_breakout(j, side, depth); breaks_done.insert(key); pending_breaks.erase(key); }
    }
}
void D1Engine::fire_breakout(int j, int side, double depth) {
    double pc; if (!bars.prev_close(j, pc)) return; double k = atm(atm(pc) + side * cfg.strike_step);
    int nn = std::min(1 + (int)py_floordiv(depth, cfg.pairs_per_depth_step), cfg.max_pairs);
    for (int r = 0; r < 2; ++r) { submit(r, k, nn, -1, R_BRK); ladder_event(r, j); }
    long ex = py_round_int(cfg.extra_a + cfg.extra_b * depth); ex = std::max<long>(0, std::min<long>(ex, cfg.max_extra));
    if (ex) submit(side > 0 ? PE : CE, k, (int)ex, -1, R_BRKX); note_body(t);
}
bool D1Engine::solo_strike(int r, int j, double& k) {
    double pc; if (!bars.prev_close(j, pc)) return false; double a0 = atm(pc); if (!last_has[r]) { k = a0; return true; }
    int best = -1; double bd = 0; double lim = cfg.ladder_strike_window * cfg.strike_step;
    for (int i = 0; i < S.nK; ++i) { if (!(std::fabs(S.K[i] - a0) <= lim)) continue; double p = obar_prev_close(r, S.K[i], j); if (isnan_(p)) p = option_ltp(r, S.K[i]); if (isnan_(p)) p = 1e9; double d = std::fabs(p - last_sale[r]); if (best < 0 || d < bd) { best = i; bd = d; } }
    if (best < 0) return false; k = S.K[best]; return true;
}
void D1Engine::ladder(int j) {
    double st = cfg.strike_step * cfg.ladder_step; int lo = std::max(j - cfg.ladder_gate_min, 0), hi = j; if (bars.completed() < 1) return;
    for (int r = 0; r < 2; ++r) {
        if (!ref_has[r] || j < ladder_from[r]) continue; double ref = ladder_ref[r]; int hh = std::min(hi, bars.completed());
        if (r == CE) {
            double mn = bars.low[lo]; for (int i = lo + 1; i < hh; ++i) mn = std::min(mn, bars.low[i]);
            if (bars.cl < mn && bars.cl < ref - st) { int nn = std::max(1, (int)py_floordiv(ref - bars.cl, st)); ladder_ref[r] = ref - st * nn; double k; if (solo_strike(r, j, k) && submit(r, k, 1, -1, R_LADDER)) note_body(t); }
        } else {
            double mx = bars.high[lo]; for (int i = lo + 1; i < hh; ++i) mx = std::max(mx, bars.high[i]);
            if (bars.ch > mx && bars.ch > ref + st) { int nn = std::max(1, (int)py_floordiv(bars.ch - ref, st)); ladder_ref[r] = ref + st * nn; double k; if (solo_strike(r, j, k) && submit(r, k, 1, -1, R_LADDER)) note_body(t); }
        }
    }
}
void D1Engine::stops(int j) {
    std::vector<Book::SK> snap = book.shorts;
    for (auto& s : snap) {
        if (s.lots.empty()) continue; double now = obar_run_high(s.r, (double)s.k, j); if (isnan_(now)) continue; int hit = 0;
        for (auto& l : s.lots) if (l.minute < j && l.entry > 0 && now / l.entry >= cfg.stop_ratio) ++hit;
        auto ps = pending_stop.find({s.r, s.k}); hit -= (ps == pending_stop.end() ? 0 : ps->second);
        if (hit > 0 && submit(s.r, (double)s.k, hit, +1, R_STOP)) note_body(t);
    }
}
void D1Engine::wing_controller(int j) {
    if (!wing_has) return; if (!(t >= wing_last + cfg.wing_delay_s || t >= wing_first + 2 * cfg.wing_delay_s)) return; wing_has = false;
    double pc; if (!bars.prev_close(j, pc)) return;
    for (int r = 0; r < 2; ++r) {
        int sg = r == CE ? 1 : -1; int gap = book.short_count(r, true) - book.wing_count(r, true);
        if (gap > 0) {
            double atm_px = option_ltp(r, atm(pc)); double target = cfg.wing_premium_frac * atm_px; if (!(target == target && target > 0)) continue;
            int best = -1; double bd = 0;
            for (int i = 0; i < S.nK; ++i) { if (sg * (S.K[i] - pc) <= 0) continue; double p = option_ltp(r, S.K[i]); if (p == p && p > 0) { double d = std::fabs(std::log(p / target)); if (best < 0 || d < bd) { bd = d; best = i; } } }
            if (best >= 0) submit(r, S.K[best], gap, +1, R_WBUY);
        } else if (gap < 0) {
            int excess = -gap; std::vector<std::pair<long, long>> held; for (auto& w : book.wings) if (w[0] == r && w[2] > 0) held.push_back({w[1], w[2]});
            std::stable_sort(held.begin(), held.end(), [&](const std::pair<long, long>& a, const std::pair<long, long>& b) { return -sg * ((double)a.first - pc) < -sg * ((double)b.first - pc); });
            for (auto& h : held) { if (excess <= 0) break; int nn = (int)std::min<long>(h.second, excess); excess -= nn; submit(r, (double)h.first, nn, -1, R_WSELL); }
        }
    }
}
void D1Engine::lump(int j) {
    if (done_lump || t < cfg.lump_time_s() || t > cfg.lump_time_s() + 600) return; done_lump = true;
    int s_ce = book.short_count(CE, false), s_pe = book.short_count(PE, false); int r = s_ce > s_pe ? CE : PE; int sg = r == CE ? 1 : -1; int nn = (int)py_round_int(cfg.lump_ratio * std::max(s_ce, s_pe));
    double pc; if (nn <= 0 || !bars.prev_close(j, pc)) return; double a = atm(pc); double straddle = option_ltp(CE, a) + option_ltp(PE, a); double sigma = straddle / (0.7979 * pc);
    if (!(sigma == sigma && sigma > 0)) return; double k = atm(pc * (1 + (double)sg * cfg.lump_sigma_mult * sigma)); submit(r, k, nn, +1, R_LUMP);
}
void D1Engine::step() {
    int j, s; pos(j, s); if (j < 0) return; double sp = spot(); if (isnan_(sp)) return;
    bars.tick(j, sp); sample_options(j, sp);
    if (cfg.has_stop) { if (stopped) return; if (t >= next_stop_check) { next_stop_check = t + cfg.cycle_stop_check_s; if (book_mtm() <= -cfg.cycle_stop_rupees) { cycle_stop(); return; } } }
    opening_wings(j); scheduled(j); breakout(j, sp); ladder(j); stops(j); wing_controller(j); lump(j);
}
D1Result D1Engine::run() {
    for (int tt = OPEN_S; tt <= OPEN_S + 390 * 60; ++tt) { t = (double)tt; step(); }
    D1Result r; r.fills = fills; r.orders = orders_n; r.rejected = rejected_n; r.stopped = stopped; r.stop_time = stop_time; r.book = book; return r;
}
}  // namespace a8
