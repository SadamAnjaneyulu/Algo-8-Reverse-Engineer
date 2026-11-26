"""Book-state study step 1 (plan BODY_REACTIVE_BOOK_PLAN.md): reconstruct the book (all modules, D-1) at each event / control second (table S) and each cycle-minute (table M): net delta, gamma, ITM short lots, distance to the outermost short strikes, MTM P&L, sigma*sqrt(T) from the ATM straddle, target-strike premium.
Outputs outputs/bl_bk_S.pkl.gz, bl_bk_M.pkl.gz"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import norm
O = load_orders(); CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); ch = Chain(); S0 = pd.read_pickle(f'{OUT}/bl_trg_band.pkl.gz'); PM = pd.read_pickle(f'{OUT}/bl_trg_panel.pkl.gz'); Pr = pd.read_csv(f'{OUT}/bl_react_pairs.csv'); CAP = 2e7
class CycleBook:
    def __init__(s, u, e, unit):
        s.u, s.e, s.unit = u, e, unit; c = ch.cyc(u, e); s.K = np.array(c['strikes'], dtype=float); s.step = ref.STEP[u]; s.sp = pd.Series(np.array(c[(0, 'spot')], dtype=float)).ffill().bfill().values
        s.close = {cp: pd.DataFrame(np.array(c[(0, cp, 'close')], dtype=float)).T.ffill().T.values for cp in ('CE', 'PE')}                       # K x 375, forward-filled along time
        z = O[(O.und == u) & (O.expiry == e) & (O.dayno == 0)].sort_values(['te', 'row']); s.z = z; cont = sorted(set(zip(z.cp, z.strike.astype(int)))); s.cont = cont; ci = {k: i for i, k in enumerate(cont)}; n, m = len(z), len(cont)
        M = np.zeros((n, m)); CASH = np.zeros(n); LP = np.full((n, m), np.nan); lp = np.full(m, np.nan); cash = 0.0
        for i, r in enumerate(z.itertuples()):
            j = ci[(r.cp, int(r.strike))]; sl = r.lots if r.side == 'Buy' else -r.lots; M[i, j] = sl; cash += -sl * r.px_avg * unit; CASH[i] = cash; lp[j] = r.px_avg; LP[i] = lp
        s.te = z.te.values; s.C = np.cumsum(M, axis=0); s.CASH = CASH; s.LP = LP; s.kv = np.array([k[1] for k in cont], dtype=float); s.isce = np.array([k[0] == 'CE' for k in cont]); s.kidx = np.array([int(np.argmin(np.abs(s.K - k))) if abs(s.K[int(np.argmin(np.abs(s.K - k)))] - k) < 1 else -1 for k in s.kv])
    def straddle(s, S, pm):
        a = int(np.argmin(np.abs(s.K - S))); return s.close['CE'][a, pm] + s.close['PE'][a, pm]
    def sig(s, S, pm):
        st = s.straddle(S, pm); return st / (0.7979 * S) if st == st and st > 0 else np.nan
    def state(s, t, S, pm, pnl_only=False):
        i = np.searchsorted(s.te, t - 3, side='left'); m = len(s.kv)
        net = s.C[i - 1] if i > 0 else np.zeros(m); cash = s.CASH[i - 1] if i > 0 else 0.0; lp = s.LP[i - 1] if i > 0 else np.full(m, np.nan)
        px = np.where(s.kidx >= 0, np.where(s.isce, s.close['CE'][np.maximum(s.kidx, 0), pm], s.close['PE'][np.maximum(s.kidx, 0), pm]), np.nan); px = np.where(np.isnan(px), lp, px); px = np.where(np.isnan(px), 0.0, px)
        pnl = cash + float(np.sum(net * s.unit * px)); out = dict(pnl_pct=pnl / CAP * 100)
        if pnl_only: return out
        sg = s.sig(S, pm); out['sig'] = sg
        if not (sg == sg) or sg <= 0: return out | dict(delta=np.nan)
        d1 = np.log(S / s.kv) / sg + sg / 2; nd = norm.cdf(d1); dl = np.where(s.isce, nd, nd - 1); gm = norm.pdf(d1) / (S * sg)
        sh = np.where(net < 0, -net, 0.0); itm = np.where(s.isce, s.kv < S, s.kv > S)
        sce = s.isce & (net < 0); spe = (~s.isce) & (net < 0)
        out.update(delta=float(np.sum(net * dl)), delta_ce=float(np.sum(net[s.isce] * dl[s.isce])), delta_pe=float(np.sum(net[~s.isce] * dl[~s.isce])), gamma=float(np.sum(net * gm) * S * 0.01), short_lots=float(sh.sum()), itm_short=float(np.sum(sh * itm)), net_lots=float(net.sum()),
                   dce_out=(float((s.kv[sce].max() - S) / s.step) if sce.any() else np.nan), dpe_out=(float((S - s.kv[spe].min()) / s.step) if spe.any() else np.nan), dce_in=(float((s.kv[sce].min() - S) / s.step) if sce.any() else np.nan), dpe_in=(float((S - s.kv[spe].max()) / s.step) if spe.any() else np.nan))
        return out
    def pair_delta(s, S, pm, k):
        sg = s.sig(S, pm)
        if not (sg == sg) or sg <= 0: return np.nan
        d1 = np.log(S / k) / sg + sg / 2; return float(-(2 * norm.cdf(d1) - 1))        # delta added to the book (lots) by selling one CE and one PE at strike k
    def pairprem(s, k, pm):
        a = int(np.argmin(np.abs(s.K - k)))
        return s.close['CE'][a, pm] + s.close['PE'][a, pm] if abs(s.K[a] - k) < 1 else np.nan
def feats(cb, t, S, side):
    j = int((t - 33300) // 60); pm = min(max(j - 1, 0), 374); f = cb.state(t, S, pm); sg = f.get('sig', np.nan)
    for lag in (300, 900, 1800):
        t2 = t - lag; j2 = int((t2 - 33300) // 60); pm2 = min(max(j2 - 1, 0), 374); S2 = cb.sp[max(j2 - 1, 0)]; g = cb.state(t2, S2, pm2)
        f[f'pnl_chg{lag // 60}'] = f['pnl_pct'] - g['pnl_pct']; f[f'delta_chg{lag // 60}'] = f.get('delta', np.nan) - g.get('delta', np.nan); f[f'sig_chg{lag // 60}'] = (sg / g['sig'] - 1) if (g.get('sig', np.nan) == g.get('sig', np.nan) and sg == sg) else np.nan
    atm = cb.K[np.argmin(np.abs(cb.K - S))]; tgt = atm + side * cb.step; pp = [cb.pairprem(tgt, max(pm - q, 0)) for q in range(0, 61)]; pp = np.array(pp, dtype=float)
    f['prem_tgt'] = pp[0]; f['prem_ratio_atm'] = pp[0] / cb.straddle(S, pm) if cb.straddle(S, pm) > 0 else np.nan; w = pp[1:]; f['prem_pos60'] = (pp[0] - np.nanmin(w)) / max(np.nanmax(w) - np.nanmin(w), 1e-6) if np.isfinite(w).sum() > 5 else np.nan; f['prem_chg15'] = pp[0] / pp[15] - 1 if pp[15] > 0 else np.nan
    f['tgt'] = tgt; f['pair_delta_1lot'] = cb.pair_delta(S, pm, tgt); d = f.get('delta', np.nan); f['delta_vs_move'] = -side * d if d == d else np.nan; f['delta_vs_move_norm'] = f['delta_vs_move'] / (f.get('short_lots', 0) + 1) if d == d else np.nan; f['side'] = side
    f['dist_out_move'] = (f.get('dce_out', np.nan) if side > 0 else f.get('dpe_out', np.nan)); f['dist_out_opp'] = (f.get('dpe_out', np.nan) if side > 0 else f.get('dce_out', np.nan)); f['dist_in_move'] = (f.get('dce_in', np.nan) if side > 0 else f.get('dpe_in', np.nan)); f['dist_in_opp'] = (f.get('dpe_in', np.nan) if side > 0 else f.get('dce_in', np.nan))
    return f
unit = {(r.und, r.expiry): r.unit for r in CY.itertuples()}; books = {}
def book(u, e):
    if (u, e) not in books: books[(u, e)] = CycleBook(u, e, unit[(u, e)])
    return books[(u, e)]
# table S
rows = []
for idx, r in enumerate(S0.itertuples()):
    cb = book(r.und, r.expiry); side = 1 if S0.pos_N60.values[idx] >= 0 else -1; f = feats(cb, r.t, r.live, side); f['row'] = idx; rows.append(f)
BS = pd.DataFrame(rows); BS = pd.concat([S0[['cid', 'und', 'expiry', 'y', 't', 'j', 'strike', 'atm', 'step', 'live', 'v2']].reset_index(drop=True), S0[['pos_N60']].reset_index(drop=True), BS.drop(columns=['row'])], axis=1); BS.to_pickle(f'{OUT}/bl_bk_S.pkl.gz'); print('S', BS.shape)
# event lots and delta change of the pair itself (mechanism)
ev = BS[BS.y == 1].copy(); lots = Pr[Pr.reactive].groupby(['und', 'expiry', 'te']).lots_ce.sum().rename('pair_lots').reset_index().rename(columns={'te': 't'}); ev = ev.merge(lots, on=['und', 'expiry', 't'], how='left'); print('events with lots', ev.pair_lots.notna().sum(), 'of', len(ev))
# table M
rows = []
for r in PM.itertuples():
    cb = book(r.und, r.expiry); t = 33300 + 60 * r.j; S = cb.sp[r.j - 1]; side = r.side; f = feats(cb, t, S, side); f['cid'] = r.cid; f['j'] = r.j; rows.append(f)
BM = pd.DataFrame(rows); BM = pd.concat([PM.reset_index(drop=True)[['cid', 'und', 'expiry', 'j', 'y', 'n_pairs', 'bk60', 'bkLA60', 'bk45', 'bk90', 'posprev60', 'depth60', 'run60', 'width60', 'min_since_1030', 'v2', 'age_pair', 'age_react', 'age_sell', 'age_bb', 'age_oth', 'n_react_sofar']], BM.drop(columns=['cid', 'j'], errors='ignore')], axis=1); BM.to_pickle(f'{OUT}/bl_bk_M.pkl.gz'); print('M', BM.shape)
print(BS[BS.y == 1][['delta', 'delta_vs_move', 'short_lots', 'itm_short', 'pnl_pct', 'sig', 'prem_tgt']].describe().round(2).T); print(BS[BS.y == 0][['delta', 'delta_vs_move', 'short_lots', 'itm_short', 'pnl_pct', 'sig', 'prem_tgt']].describe().round(2).T)
ev.to_pickle(f'{OUT}/bl_bk_events.pkl.gz')
