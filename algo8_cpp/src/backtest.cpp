#include "algo8/backtest.hpp"
#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
namespace a8 {
// ---------------------------------------------------------------- dates
static long ordinal(const std::string& d) { int y = std::stoi(d.substr(0, 4)), m = std::stoi(d.substr(5, 2)), dd = std::stoi(d.substr(8, 2)); y -= m <= 2; long era = (y >= 0 ? y : y - 399) / 400; long yoe = y - era * 400; long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + dd - 1; long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy; return era * 146097 + doe - 719468 + 719163; }
static double epoch_of(const std::string& day, double sec) { return (double)ordinal(day) * 86400.0 + sec; }
static void civil_from_ordinal(long o, int& y, int& m, int& d) {   // proleptic Gregorian, ordinal 1 = 0001-01-01
    long z = o - 719163 + 719468; long era = (z >= 0 ? z : z - 146096) / 146097; long doe = z - era * 146097; long yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365; long yy = yoe + era * 400; long doy = doe - (365 * yoe + yoe / 4 - yoe / 100); long mp = (5 * doy + 2) / 153;
    d = (int)(doy - (153 * mp + 2) / 5 + 1); m = (int)(mp < 10 ? mp + 3 : mp - 9); y = (int)(yy + (m <= 2)); }
static std::string iso_week(const std::string& dstr) {                // '%G-W%V'
    long o = ordinal(dstr); int wd = (int)((o + 6) % 7);               // Monday = 0
    long thu = o - wd + 3; int y, m, d; civil_from_ordinal(thu, y, m, d); char b[16]; std::snprintf(b, sizeof b, "%04d-01-01", y); long jan1 = ordinal(b);
    int wk = (int)((thu - jan1) / 7) + 1; char r[24]; std::snprintf(r, sizeof r, "%04d-W%02d", y, wk); return r; }
// ---------------------------------------------------------------- costs (backtest/bt/account.py)
static double stt_sell(const std::string& d) { return d < "2024-10-01" ? 0.000625 : (d < "2026-04-01" ? 0.001 : 0.0015); }
static double order_costs(const std::string& und, const std::string& day, int side, double value, double mult) {
    const double BROK = 20.0, GST = 0.18, SEBI = 0.000001, STAMP = 0.00003; double TXN = und == "NIFTY" ? 0.00035 : 0.000325;
    double b = BROK, t = TXN * value, s = SEBI * value, g = GST * (b + t + s), stamp = side > 0 ? STAMP * value : 0.0, stt = side < 0 ? stt_sell(day) * value : 0.0; return mult * (b + t + s + g + stamp + stt);
}
// ---------------------------------------------------------------- csv helpers
static std::vector<std::string> split_csv(const std::string& l) { std::vector<std::string> o; std::string c; std::stringstream ss(l); while (std::getline(ss, c, ',')) o.push_back(c); return o; }
Waves Waves::load(const std::string& csv) {
    Waves w; std::ifstream f(csv); if (!f) throw std::runtime_error("cannot open " + csv); std::string l; std::getline(f, l);       // header: und,version,t,lots
    while (std::getline(f, l)) { if (l.empty()) continue; auto c = split_csv(l); w.by_und_version[{c[0], c[1]}].push_back({std::stod(c[2]), std::stoi(c[3])}); } return w;
}
std::vector<CycleTask> load_cycles(const std::string& csv) {
    std::vector<CycleTask> v; std::ifstream f(csv); if (!f) throw std::runtime_error("cannot open " + csv); std::string l; std::getline(f, l);       // header: und,expiry,d1,d0,lot
    while (std::getline(f, l)) { if (l.empty()) continue; auto c = split_csv(l); v.push_back({c[0], c[1], c[2], c[3], std::stoi(c[4])}); } return v;
}
std::string split_of(const std::string& d0) { return ("2026-06-22" <= d0 && d0 <= "2026-10-22") ? "DEV" : (d0 >= "2026-10-23" ? "POST" : "PRE"); }
std::string user_split(const std::string& d1, const std::string& d0) { return (d1 <= "2025-11-17" && "2025-11-17" < d0) ? "EMBARGO" : (d0 <= "2025-11-17" ? "USER_IS" : "USER_OOS"); }
// ---------------------------------------------------------------- one cycle
struct AF { std::string day; double t; int cp; long k; int sg; int n; double p; int orders; };
CycleResult run_cycle(const CycleTask& tk, const std::string& dir, const Waves& W, const RunParams& P) {
    CycleResult R; R.und = tk.und; R.expiry = tk.expiry; R.d1 = tk.d1; R.d0 = tk.d0; R.lot = tk.lot; const int lot = tk.lot; const double cm = P.cost_mult;
    Session s1 = Session::load(dir + "/" + tk.und + "_" + tk.expiry + "_" + tk.d1 + ".a8s"), s0 = Session::load(dir + "/" + tk.und + "_" + tk.expiry + "_" + tk.d0 + ".a8s");
    bool has_stop = P.stop_rupees > 0; D1Config c1 = d1_config_for(tk.und, tk.d1, lot, has_stop, P.stop_rupees); D1Engine e1(c1, s1); D1Result r1 = e1.run();
    std::vector<AF> F; for (auto& f : r1.fills) F.push_back({tk.d1, f.ts, f.right, (long)f.strike, f.side, f.lots, f.price, 1});
    R.d1_stopped = r1.stopped; bool d0_stopped = false; int stop_minute = -1; std::vector<Event> ev0; const int fz = tk.und == "NIFTY" ? 27 : 50; const double step = tk.und == "NIFTY" ? 50.0 : 100.0;
    if (r1.stopped) stop_minute = (int)std::floor((r1.stop_time - OPEN_S) / 60.0);
    if (!r1.stopped) {
        Opening op; std::vector<std::array<long, 3>> sh; std::vector<std::vector<Lot>> shl;
        std::vector<const Book::SK*> keys; for (auto& s : r1.book.shorts) keys.push_back(&s); std::sort(keys.begin(), keys.end(), [](const Book::SK* a, const Book::SK* b) { return a->r != b->r ? a->r < b->r : a->k < b->k; });
        for (auto* s : keys) for (auto& l : s->lots) op.lots.push_back({(double)s->r, (double)s->k, l.entry});
        auto wl = r1.book.wings; std::sort(wl.begin(), wl.end()); for (auto& w : wl) if (w[2] > 0) op.longs.push_back({1, w[0], w[1], w[2]});
        auto lp = r1.book.lump; std::sort(lp.begin(), lp.end()); for (auto& w : lp) if (w[2] > 0) op.longs.push_back({2, w[0], w[1], w[2]});
        double cash = 0.0; for (auto& f : r1.fills) cash += (f.side < 0 ? 1.0 : -1.0) * f.price * f.lots * (double)lot; op.cash = cash;
        bool ok = true; for (auto& l : op.lots) if (s0.index_of(l[1]) < 0) ok = false; for (auto& g : op.longs) if (s0.index_of((double)g[2]) < 0) ok = false;
        if (!ok) R.handoff_error = true;
        else {
            D0Config c0; std::string ver = tk.d1 >= "2026-09-16" ? "V2" : "V1"; auto it = W.by_und_version.find({tk.und, ver}); if (it != W.by_und_version.end()) c0.waves = it->second;
            c0.cycle_stop_rupees = has_stop ? P.stop_rupees : 1e18; D0Engine e0(c0, s0, (double)lot, step, op); D0Result r0 = e0.run(); d0_stopped = r0.stopped; ev0 = r0.events;
            if (d0_stopped) { int mj = 1 << 30; for (auto& e : ev0) if (e.cls == C_STOP) mj = std::min(mj, e.j); stop_minute = mj; }
        }
    }
    R.d0_stopped = d0_stopped; R.stop_minute = stop_minute;
    for (auto& e : ev0) {
        double t = OPEN_S + 60.0 * e.j;
        if (e.cls == C_STOP) { std::vector<std::pair<int, int>> agg; for (auto& pr : e.parts) { bool f = false; for (auto& a : agg) if (a.first == pr.first) { a.second += pr.second; f = true; break; } if (!f) agg.push_back(pr); }
            for (auto& a : agg) F.push_back({tk.d0, t, e.cp, e.strike, a.first == 1 ? -1 : 1, a.second, e.px, (a.second + fz - 1) / fz}); }
        else F.push_back({tk.d0, t, e.cp, e.strike, e.side > 0 ? 1 : -1, e.lots, e.px, (e.lots + fz - 1) / fz});
    }
    // ---- accounting
    std::stable_sort(F.begin(), F.end(), [](const AF& a, const AF& b) { return epoch_of(a.day, a.t) < epoch_of(b.day, b.t); });
    double gross = 0, slip = 0, costs = 0; int n_orders = 0; std::vector<std::pair<std::pair<int, long>, long>> pos; auto bump = [&](int cp, long k, long q) { for (auto& e : pos) if (e.first.first == cp && e.first.second == k) { e.second += q; return; } pos.push_back({{cp, k}, q}); };
    const double BROK = 20.0, GSTR = 0.18;
    for (auto& f : F) {
        double p = f.p; if (!(p == p) || p <= 0) p = 0.05; double sl = std::max(0.10, 0.005 * p) * P.slip_mult; double pe = std::max(p + f.sg * sl, 0.05); double vref = p * f.n * lot, vexe = pe * f.n * lot;
        gross += -f.sg * vref; slip += f.sg * (pe - p) * f.n * lot; costs += order_costs(tk.und, f.day, f.sg, vexe, cm) + (f.orders - 1) * BROK * cm * (1 + GSTR); n_orders += f.orders; bump(f.cp, f.k, (long)f.sg * f.n);
    }
    double settle = 0; int resid = 0; double s0c = s0.sp[CLOSE][s0.n - 1]; for (auto& e : pos) if (e.second != 0) { ++resid; double iv = e.first.first == CE ? std::max(s0c - (double)e.first.second, 0.0) : std::max((double)e.first.second - s0c, 0.0); settle += e.second * iv * lot; }
    double net = (gross - slip) + settle - costs; R.gross = gross + settle; R.slippage = slip; R.costs = costs; R.net = net; R.settle = settle; R.n_orders = n_orders; R.n_fills = (int)F.size(); R.residual = resid;
    // ---- equity path (net, minute closes)
    int last_d0 = r1.stopped ? -1 : (d0_stopped ? std::min(374, stop_minute + 1) : 374); size_t fi = 0; double cash = 0, cc = 0; std::vector<std::pair<std::pair<int, long>, long>> pp;
    auto bump2 = [&](int cp, long k, long q) { for (auto& e : pp) if (e.first.first == cp && e.first.second == k) { e.second += q; return; } pp.push_back({{cp, k}, q}); };
    for (int di = 0; di < 2; ++di) {
        const std::string& day = di == 0 ? tk.d1 : tk.d0; const Session& ss = di == 0 ? s1 : s0; int lj = di == 0 ? 374 : last_d0;
        for (int j = 0; j <= lj; ++j) {
            double tend = epoch_of(day, OPEN_S + 60.0 * (j + 1));
            while (fi < F.size() && epoch_of(F[fi].day, F[fi].t) < tend) { auto& f = F[fi]; double p = (f.p == f.p && f.p > 0) ? f.p : 0.05; double pe = std::max(p + f.sg * (std::max(0.10, 0.005 * p) * P.slip_mult), 0.05); cash += -f.sg * pe * f.n * lot; cc += order_costs(tk.und, f.day, f.sg, pe * f.n * lot, cm) + (f.orders - 1) * BROK * cm * (1 + GSTR); bump2(f.cp, f.k, (long)f.sg * f.n); ++fi; }
            double mtm = 0; for (auto& e : pp) { if (e.second == 0) continue; int x = ss.index_of((double)e.first.second); double pr = x >= 0 ? ss.o(e.first.first, CLOSE, x, std::min(j, 374)) : NaN; if (pr == pr) mtm += e.second * pr * lot; }
            R.path.push_back({tend, cash + mtm - cc});
        }
    }
    R.path.push_back({epoch_of(tk.d0, 16 * 3600), net}); R.min_path = R.max_path = R.path[0].second; for (auto& p : R.path) { R.min_path = std::min(R.min_path, p.second); R.max_path = std::max(R.max_path, p.second); }
    return R;
}
// ---------------------------------------------------------------- metrics (backtest/bt/metrics.py)
Metrics compute_metrics(const std::vector<const CycleResult*>& v, const std::string& label) {
    Metrics m; m.label = label; m.cycles = (int)v.size(); if (v.empty()) return m; const double cap = CAPITAL_RS;
    std::map<std::string, double> wk; for (auto* r : v) wk[iso_week(r->d0)] += r->net; std::vector<double> rr; for (auto& e : wk) rr.push_back(e.second / cap); int n = (int)rr.size(); m.weeks = n;
    double mean = 0; for (double x : rr) mean += x; mean /= n; double sd = NaN; if (n > 1) { double q = 0; for (double x : rr) q += (x - mean) * (x - mean); sd = std::sqrt(q / (n - 1)); }
    double dn2 = 0; for (double x : rr) if (x < 0) dn2 += x * x; double dsd = std::sqrt(dn2 / n);
    // equity curve from every cycle's path increments
    std::vector<std::pair<double, double>> inc; for (auto* r : v) { double prev = 0; for (auto& p : r->path) { inc.push_back({p.first, p.second - prev}); prev = p.second; } } std::sort(inc.begin(), inc.end());
    std::vector<double> t, eq; double cum = 0; for (auto& e : inc) { cum += e.second; t.push_back(e.first); eq.push_back(cap + cum); }
    double peak = cap, mdd = 0, mddp = 0, longest = 0, cur = 0, start = t.empty() ? 0 : t[0]; bool has_start = false;
    for (size_t k = 0; k < eq.size(); ++k) { peak = std::max(peak, eq[k]); double dd = eq[k] - peak; mdd = std::min(mdd, dd); mddp = std::min(mddp, dd / peak); if (eq[k] >= peak - 1e-9) { start = t[k]; has_start = true; cur = 0; } else { cur = (t[k] - (has_start ? start : t[0])) / 86400.0; longest = std::max(longest, cur); } }
    std::string dmin = v[0]->d1, dmax = v[0]->d0; for (auto* r : v) { dmin = std::min(dmin, r->d1); dmax = std::max(dmax, r->d0); }
    double span = std::max((double)(ordinal(dmax) - ordinal(dmin)) / 365.25, 1e-9); double tot = 0, gr = 0, co = 0, sl = 0, wins = 0, losses = 0; int nw = 0, nl = 0; std::vector<double> nets; int stops = 0, ns;
    for (auto* r : v) { tot += r->net; gr += r->gross; co += r->costs; sl += r->slippage; nets.push_back(r->net); if (r->net > 0) { wins += r->net; ++nw; } else { losses += r->net; ++nl; } if (r->d1_stopped || r->d0_stopped) ++stops; }
    ns = (int)nets.size(); std::vector<double> sorted = nets; std::sort(sorted.begin(), sorted.end());
    m.net = tot; m.gross = gr; m.costs = co; m.slippage = sl; m.cum_return_pct = 100 * tot / cap; m.ann_return_pct = 100 * (tot / cap / span); m.vol_ann_pct = 100 * sd * std::sqrt(52.0);
    m.sharpe = (sd == sd && sd > 0) ? mean / sd * std::sqrt(52.0) : NaN; m.sortino = dsd > 0 ? mean / dsd * std::sqrt(52.0) : NaN; m.max_dd_rs = mdd; m.max_dd_pct = 100 * mddp; m.longest_dd_days = longest;
    m.win_rate_pct = 100.0 * nw / ns; m.avg_win = nw ? wins / nw : 0; m.avg_loss = nl ? losses / nl : 0; m.profit_factor = (nl && losses != 0) ? wins / std::fabs(losses) : std::numeric_limits<double>::infinity(); m.expectancy = tot / ns;
    m.median_cycle = ns % 2 ? sorted[ns / 2] : 0.5 * (sorted[ns / 2 - 1] + sorted[ns / 2]); m.worst = sorted.front(); m.best = sorted.back(); int k5 = std::max((int)std::ceil(0.05 * ns), 1); double q = 0; for (int i = 0; i < k5; ++i) q += sorted[i]; m.cvar5 = q / k5;
    if (nw && wins > 0) { std::vector<double> w; for (double x : nets) if (x > 0) w.push_back(x); std::sort(w.rbegin(), w.rend()); double s5 = 0; for (size_t i = 0; i < std::min<size_t>(5, w.size()); ++i) s5 += w[i]; m.top5_share_pct = 100 * s5 / wins; }
    m.stop_rate_pct = 100.0 * stops / ns; return m;
}
}  // namespace a8
