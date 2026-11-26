#include "algo8/d0_engine.hpp"
namespace a8 {
D0Engine::D0Engine(const D0Config& c, const Session& s, double u, double st, const Opening& op) : cfg(c), S(s), unit(u), step(st), lots(op.lots), longs(op.longs), cash(op.cash) {
    for (auto& l : lots) if (S.index_of(l[1]) < 0) throw std::runtime_error("carried lot outside the chain");
    breakout_fires();
    for (auto& w : cfg.waves) wave_by_minute[(int)py_floordiv(w.first - OPEN_S, 60.0)].push_back(w.second);
}
double D0Engine::px(int cp, double k, int j, int f) const {
    int x = S.index_of((double)(long)k); if (x < 0) return NaN; int jj = std::min(std::max(j, 0), cfg.last_minute); return S.o(cp, f, x, jj);
}
void D0Engine::breakout_fires() {
    const auto& h = S.sp[HIGH]; const auto& l = S.sp[LOW]; std::set<std::pair<int, int>> done;
    for (int j = cfg.breakout_start_min; j <= cfg.breakout_end_min; ++j) {
        int clock = OPEN_S + 60 * j; int b0 = (clock / 1800) * 1800; int a = (int)std::ceil((double)(b0 - 3600 - OPEN_S) / 60.0), e = (int)std::ceil((double)(b0 - OPEN_S) / 60.0);
        if (e - std::max(a, 0) < 2) continue; int aa = std::max(a, 0); double H = h[aa], L = l[aa]; for (int i = aa + 1; i < e; ++i) { H = std::max(H, h[i]); L = std::min(L, l[i]); }
        for (int s : {1, -1}) { bool fl = s == 1 ? h[j] > H : l[j] < L; if (fl && !done.count({b0, s})) { fires[j].push_back(s); done.insert({b0, s}); } }
    }
}
void D0Engine::rec(Cls c, int cp, int j, double k, int n, int side, double p, const std::vector<std::pair<int, int>>& parts) {
    if (c == C_BODY_SELL) decisions[j] += 1; events.push_back(Event{c, cp, j, (long)k, n, parts, side, p});
}
bool D0Engine::risk_blocks(int cp, int n, int j) {
    bool why = false;
    if (shorts_on(cp) + n > cfg.max_short_lots_per_right) why = true; else if ((decisions.count(j) ? decisions[j] : 0) >= cfg.max_sell_decisions_per_minute) why = true;
    if (!why) { max_short_seen = std::max(max_short_seen, shorts_on(cp) + n); return false; } return true;
}
double D0Engine::mtm(int j) const {
    double v = cash, u = unit;
    for (auto& l : lots) { double p = px((int)l[0], l[1], j); if (!isnan_(p)) v -= p * u; }
    for (auto& g : longs) { double p = px((int)g[1], (double)g[2], j); if (!isnan_(p)) v += (double)g[3] * p * u; }
    return v;
}
void D0Engine::cycle_stop(int j) {
    struct E { int cp; long k; int n; std::vector<std::pair<int, int>> parts; }; std::vector<E> agg; auto get = [&](int cp, long k) -> E& { for (auto& e : agg) if (e.cp == cp && e.k == k) return e; agg.push_back({cp, k, 0, {}}); return agg.back(); };
    for (auto& l : lots) { auto& e = get((int)l[0], (long)l[1]); e.n += 1; e.parts.push_back({0, 1}); }
    for (auto& g : longs) { auto& e = get((int)g[1], g[2]); e.n += (int)g[3]; }
    for (auto& g : longs) { auto& e = get((int)g[1], g[2]); e.parts.push_back({1, (int)g[3]}); }
    for (auto& e : agg) rec(C_STOP, e.cp, j, (double)e.k, e.n, 0, px(e.cp, (double)e.k, j), e.parts);
    stopped = true;
}
void D0Engine::clearance(int j) {
    struct E { int cp; long k; int n; }; std::vector<E> agg; for (auto& l : lots) { bool f = false; for (auto& e : agg) if (e.cp == (int)l[0] && e.k == (long)l[1]) { ++e.n; f = true; break; } if (!f) agg.push_back({(int)l[0], (long)l[1], 1}); }
    for (auto& e : agg) rec(C_BODY_BUYBACK, e.cp, j, (double)e.k, e.n, +1, px(e.cp, (double)e.k, j));
    for (auto& g : longs) { Cls c = g[0] == 0 ? C_BODY_LONG : C_WING_SELL; rec(c, (int)g[1], j, (double)g[2], (int)g[3], -1, px((int)g[1], (double)g[2], j)); }
    lots.clear(); longs.clear(); cleared = true;
}
std::array<int, 2> D0Engine::buybacks(int j) {
    std::array<int, 2> nbb = {0, 0}; std::vector<std::array<double, 3>> keep;
    if (j >= 1) {
        for (auto& L : lots) {
            int cp = (int)L[0]; double k = L[1], e = L[2]; double ph = px(cp, k, j, HIGH), pl = px(cp, k, j, LOW);
            bool hit_stop = e > 0 && ph == ph && ph >= cfg.buyback_theta * e; bool hit_tp = e > 0 && cfg.buyback_tp != 0.0 && pl == pl && pl <= cfg.buyback_tp * e;
            if (e > 0 && (hit_stop || hit_tp)) {
                double po = px(cp, k, j, OPEN); double fp = hit_stop ? (po == po ? std::max(po, cfg.buyback_theta * e) : cfg.buyback_theta * e) : (po == po ? std::min(po, cfg.buyback_tp * e) : cfg.buyback_tp * e);
                rec(C_BODY_BUYBACK, cp, j, k, 1, +1, fp); nbb[cp] += 1; double p = px(cp, k, j); cash -= (p == p ? p : e) * unit;
            } else keep.push_back(L);
        }
        lots = keep;
    }
    return nbb;
}
std::vector<D0Engine::Sell> D0Engine::sells(int j, double c0, double stp, const std::array<int, 2>& nbb) {
    std::vector<Sell> out; const auto& h = S.sp[HIGH]; const auto& l = S.sp[LOW];
    auto wb = wave_by_minute.find(j); if (wb != wave_by_minute.end()) for (int nn : wb->second) { double k = atm(c0); out.push_back({CE, k, nn, true}); out.push_back({PE, k, nn, true}); }
    if (cfg.breakout_start_min <= j && j <= cfg.breakout_end_min) { auto f = fires.find(j); if (f != fires.end()) for (int s : f->second) { double k = atm(c0) + s * step; out.push_back({CE, k, 1, true}); out.push_back({PE, k, 1, true}); } }
    for (int cp = 0; cp < 2; ++cp) {
        if (!ref_has || j < 1) continue;
        if (cfg.ladder_gate_min) {
            int lo = std::max(j - cfg.ladder_gate_min, 0); bool ok;
            if (cp == CE) { double mn = l[lo]; for (int i = lo + 1; i < j; ++i) mn = std::min(mn, l[i]); ok = l[j] < mn; } else { double mx = h[lo]; for (int i = lo + 1; i < j; ++i) mx = std::max(mx, h[i]); ok = h[j] > mx; }
            if (!ok) continue;
        }
        double dv = cp == CE ? (ref[cp] - l[j]) : (h[j] - ref[cp]);
        if (dv > stp) { int nn = (int)py_floordiv(dv, stp); out.push_back({cp, atm(c0), cfg.ladder_mult ? std::min(nn, cfg.solo_lot_cap) : 1, false}); ref[cp] = cp == CE ? ref[cp] - nn * stp : ref[cp] + nn * stp; }
    }
    bool any_pair = false; for (auto& s : out) if (s.pair) any_pair = true; if (any_pair) { ref_has = true; ref[0] = ref[1] = c0; }
    for (int cp = 0; cp < 2; ++cp) { int o = cp == CE ? PE : CE; acc[cp] += cfg.counter_ratio * nbb[o]; int nn = (int)acc[cp]; acc[cp] -= nn; if (nn) out.push_back({cp, atm(c0), nn, false}); }
    return out;
}
void D0Engine::opening_wings(double c0) {
    for (int cp = 0; cp < 2; ++cp) {
        int nn = cp == CE ? cfg.opening_wing_lots / 2 : cfg.opening_wing_lots - cfg.opening_wing_lots / 2; double k = atm(c0 + (cp == CE ? 1 : -1) * cfg.opening_wing_offset_steps * step);
        rec(C_BODY_LONG, cp, 0, k, nn, +1, px(cp, k, 0)); bool f = false; for (auto& g : longs) if (g[0] == 0 && g[1] == cp && g[2] == (long)k) { g[3] += nn; f = true; break; } if (!f) longs.push_back({0, cp, (long)k, nn});
        double p = px(cp, k, 0); cash -= (p == p ? p : 0.0) * nn * unit;
    }
}
void D0Engine::hedge(int j, int jp, double c0) {
    for (int cp = 0; cp < 2; ++cp) {
        int S_ = shorts_on(cp), L_ = 0; for (auto& g : longs) if (g[1] == cp) L_ += (int)g[3]; int g = S_ - L_; double dir = cp == CE ? 1.0 : -1.0;
        if (g > 0) {
            double a = px(cp, atm(c0), jp); int best = -1; double bd = 0; bool any = false; double target = cfg.wing_premium_frac * a;
            for (int i = 0; i < S.nK; ++i) {
                double pr = S.o(cp, CLOSE, i, jp); bool otm = (S.K[i] - c0) * dir > 0; if (!(otm && std::isfinite(pr))) continue; any = true;
                double d = std::fabs(pr - target); if (best < 0 || d < bd) { bd = d; best = i; }
            }
            if (a == a && any) {
                double k = S.K[best]; rec(C_WING_BUY, cp, j, k, g, +1, px(cp, k, j)); bool f = false;
                for (auto& e : longs) if (e[0] == 1 && e[1] == cp && e[2] == (long)k) { e[3] += g; f = true; break; } if (!f) longs.push_back({1, cp, (long)k, g});
                double p = px(cp, k, j); cash -= (p == p ? p : 0.0) * g * unit;
            }
        } else if (g < 0) {
            int need = -g; std::vector<std::array<long, 4>> cand; for (auto& e : longs) if (e[1] == cp && (e[0] == 1 || e[0] == 2) && e[3] > 0) cand.push_back({e[0], e[1], e[2], 0});
            std::stable_sort(cand.begin(), cand.end(), [&](const std::array<long, 4>& a, const std::array<long, 4>& b) { return -(((double)a[2] - c0) * dir) < -(((double)b[2] - c0) * dir); });
            for (auto& c : cand) {
                if (need <= 0) break; std::array<long, 4>* e = nullptr; for (auto& q : longs) if (q[0] == c[0] && q[1] == c[1] && q[2] == c[2]) { e = &q; break; }
                int x = (int)std::min<long>(need, (*e)[3]); (*e)[3] -= x; need -= x; rec(C_WING_SELL, cp, j, (double)c[2], x, -1, px(cp, (double)c[2], j));
                double p = px(cp, (double)c[2], j); cash += (p == p ? p : 0.0) * x * unit;
                if ((*e)[3] == 0) { for (size_t q = 0; q < longs.size(); ++q) if (&longs[q] == e) { longs.erase(longs.begin() + q); break; } }
            }
        }
    }
}
D0Result D0Engine::run() {
    const auto& cl = S.sp[CLOSE]; double stp = cfg.ladder_step * step;
    for (int j = 0; j <= cfg.last_minute; ++j) {
        if (stopped) break;
        if (mtm(j) <= -cfg.cycle_stop_rupees) { cycle_stop(j); break; }
        int jp = std::max(j - 1, 0); double c0 = j > 0 ? cl[jp] : S.sp[OPEN][0];
        if (j == cfg.clearance_minute) { clearance(j); break; }
        auto nbb = buybacks(j); auto sl = sells(j, c0, stp, nbb);
        for (auto& s : sl) {
            if (S.index_of((double)(long)s.k) < 0) continue;
            if (risk_blocks(s.cp, s.n, j)) { ++rejected; continue; }
            double e = px(s.cp, s.k, jp); if (!(e == e)) e = px(s.cp, s.k, j);
            rec(C_BODY_SELL, s.cp, j, s.k, s.n, -1, e == e ? e : px(s.cp, s.k, j));
            for (int i = 0; i < s.n; ++i) lots.push_back({(double)s.cp, s.k, e}); cash += (e == e ? e : 0.0) * s.n * unit;
        }
        if (j == 0 && cfg.opening_wing_lots) opening_wings(c0);
        hedge(j, jp, c0);
    }
    D0Result r; r.events = events; r.stopped = stopped; r.cleared = cleared; r.rejected = rejected; r.max_short_seen = max_short_seen; return r;
}
}  // namespace a8
