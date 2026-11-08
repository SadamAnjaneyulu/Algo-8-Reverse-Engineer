"""Section 8 - autonomous portfolio replay of the exit controller.

The replay keeps its OWN unit-lot book and recomputes every feature from that book (same definitions as bookstate.py; equality is checked by
a teacher-forced run in tests/).  At the start of every minute m it sees only bars completed before m, its own book and its own history.
Decisions it makes itself, in this order:
  1 cycle liquidation  : verified rule, close-based book MTM <= -Rs 1.33 L (main FINDINGS)  -> close everything
  2 final liquidation  : book-level model (DEV fit, VAL threshold)                         -> close everything
  3 contract exits     : contract-minute exit model + quantity model (all lots / 1 lot / part)  [hold, partial buy-back, full exit;
                         side / basket reductions emerge when several contracts fire in the same minute]
  4 wing release       : DEV-measured ratio of wing lots released per short lot bought back, same side; long salvage at <= Rs 1 on D0 (rule)
  5 re-entry/rebalance : episode-level re-entry model; strike = |delta| nearest the DEV median of re-entry sales; wings by the DEV wing rule
Two modes, reported separately.  Mode A: inputs it does NOT decide (exogenous, arrive at their own timestamp, never ahead of time): the base entry stream = actual opening orders
that are not re-entries (ladder sales + their h_ wings) and the v_ overnight-lump module.  Platform / manual orders (m_, AlgoId 152432,
2.18811E+15) are external interventions and are not replayed.  Mode B: fully autonomous - entries come from the decoded clone rules
(alpha_grid ladders, ATM strike, 1.2 % wing budget; engine.py) and no actual order of any kind is used.  Neither mode receives actual exits,
actual future inventory or labels.  Policies: 'model' (ML controller), 'hold' (cycle-stop rule only), 'clone' (decoded rule exits).
Abstention: a contract-minute whose top model features fall outside the DEV support (0.1-99.9 % range) is held and counted as abstained.
Fills for replay decisions: 'open' (minute-m open), 'adverse' (buys at the minute high, sells at the low), 'delay1' (next minute open).
python3 analysis/exit_engine/replay.py [--fill open|adverse|delay1] -> results/autonomous_replay_metrics_<fill>.csv (+ by-cycle file)"""
import sys, os, argparse, warnings
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); sys.path.insert(0, AN); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
warnings.filterwarnings('ignore')
import lightgbm as lgb
from sklearn.metrics import f1_score
from common import orders, markets, minute_index, LOT, RES, C, SCHEDULED, split_of
import bookstate
from models import prep, feats_of, BOOK_JOIN, best_threshold
from side_basket import episodes
from engine import COSTS, STEP
from alpha_grid import LADDER_D1, LADDER_D0          # decoded entry ladder, unchanged (used by mode B only)
WING_FRAC = 0.012                                    # decoded wing budget (fraction of the straddle premium, per side), as the registered clone
CYCLE_STOP = 133000.0
PLATFORM_IDS = {'152432', '2.18811E+15'}

# ---------------------------------------------------------------- market arrays (shifted: index i = information available at start of minute i)
def prepare(m):
    if 'prep' in m: return m['prep']
    IV, DEL, GAM, VEG, THE, T = bookstate.greeks(m)
    nk, n = m['Cf'].shape
    sh = lambda A: np.hstack([np.full((A.shape[0], 1), np.nan), A[:, :-1].astype(float)])
    S = m['S']; day = m['day']; d0 = int(day.argmax()) if day.any() else None; grid = m['grid']
    Sp = np.concatenate([[S[0]], S[:-1]]); atr = m['atr1']
    mv = lambda h: (Sp - np.concatenate([np.full(h, Sp[0]), Sp[:-h]])) / atr
    hh = grid.hour * 60 + grid.minute
    ph = ((grid - grid.normalize() - pd.Timedelta('09:15:00')).total_seconds().values // 60) % 15
    P = dict(mark=sh(m['Cf']), Hp=sh(m['H']), gD=np.nan_to_num(sh(DEL)), gG=np.nan_to_num(sh(GAM)), gV=np.nan_to_num(sh(VEG)), gT=np.nan_to_num(sh(THE)), iv=sh(IV),
             DELraw=DEL, Sp=Sp, atr=atr, mv1=mv(1), mv5=mv(5), mv15=mv(15), mv30=mv(30), T=T, d0=d0,
             sd0=(Sp - S[d0]) / atr if d0 is not None else np.full(n, np.nan), spc=(Sp - S[d0 - 1]) / atr if (d0 is not None and d0 > 0) else np.full(n, np.nan),
             hh=hh, clockB=(day == 1) & (ph == 14) & (hh >= 9 * 60 + 29), gridA=(ph == 1), grid00=(grid.minute == 0) & (hh >= 13 * 60 + 30),
             isce=np.array([c == 'CE' for c, _ in m['keys']]), K=np.array([k for _, k in m['keys']], float))
    m['prep'] = P; return P

def fill_px(m, kk, i, side, mode):
    n = m['Cf'].shape[1]; Cfp = float(m['Cf'][kk, i - 1]) if i > 0 else np.nan
    if mode == 'delay1':
        j = min(i + 1, n - 1); v = float(m['O'][kk, j]); return v if np.isfinite(v) else float(m['Cf'][kk, j])
    if mode == 'adverse':
        v = float(m['H'][kk, i] if side > 0 else m['L'][kk, i]); return v if np.isfinite(v) else Cfp
    v = float(m['O'][kk, i]); return v if np.isfinite(v) else Cfp

# ---------------------------------------------------------------- book
class Book:
    def __init__(self, m):
        self.m = m; self.lot = LOT[m['und']]; self.lots = {}; self.realised = 0.0; self.had_bb = set(); self.sale_mi = {}; self.bb_mi = {}
        self.mtm_hist = []; self.orders = []; self.turnover = 0.0; self.units = 0; self.n_orders = 0
    def apply(self, k, sgn, n, px, mi, reason, record=True):
        L_ = self.lots.setdefault(k, []); pos = sum(x['sgn'] for x in L_); rem = n; closed_short = 0
        if (sgn > 0 and pos < 0) or (sgn < 0 and pos > 0):
            L_.sort(key=lambda x: (x['px'] if pos < 0 else -x['px'], x['mi']))
            take = min(rem, len(L_))
            for x in L_[:take]: self.realised += x['sgn'] * (px - x['px']) * self.lot
            del L_[:take]; rem -= take
            if pos < 0: self.had_bb.add(k); self.bb_mi.setdefault(k, []).append(mi); closed_short = take
        for _ in range(rem):
            L_.append(dict(sgn=sgn, px=px, mi=mi, carried=False, reentry=k in self.had_bb))
        if sgn < 0 and rem > 0: self.sale_mi.setdefault(k, []).append(mi)
        if record:
            self.orders.append((mi, k, sgn, n, px, reason)); self.turnover += px * self.lot * n; self.units += self.lot * n; self.n_orders += 1
        return closed_short
    def pos(self, k): return sum(x['sgn'] for x in self.lots.get(k, []))
    def mark_carried(self):
        for L_ in self.lots.values():
            for x in L_:
                if x['sgn'] < 0: x['carried'] = True
    def mtm_now(self, i, P):
        """realised + unrealised at the start of minute i with marks = close of i-1 (nan mark -> 0, as bookstate)"""
        u = 0.0
        for k, L_ in self.lots.items():
            if not L_: continue
            mk_ = P['mark'][self.m['k2i'][k], i]
            if not np.isfinite(mk_): continue                   # no print yet -> marked at entry (zero unrealised), as bookstate
            for x in L_: u += x['sgn'] * (mk_ - x['px']) * self.lot
        return self.realised + u

def last_before(lst, i):
    if not lst: return np.nan
    a = np.asarray(lst); a = a[a < i]; return float(i - a.max()) if len(a) else np.nan

def features(book, i, P):
    """CM rows (open shorts) + BM row for the start of minute i, from the book's own state"""
    m = book.m; lot = book.lot; k2i = m['k2i']; isce = P['isce']; d0 = P['d0']
    sc = {}; up = {}
    for k, L_ in book.lots.items():
        s = [x for x in L_ if x['sgn'] < 0]
        if s: sc[k] = s
    side_lots = {'CE': 0, 'PE': 0}; side_up = {'CE': 0.0, 'PE': 0.0}
    for k, s in sc.items():
        mk_ = P['mark'][k2i[k], i]
        up[k] = sum(x['px'] - mk_ for x in s) * lot if np.isfinite(mk_) else 0.0; side_lots[k[0]] += len(s); side_up[k[0]] += up[k]
    tot = side_lots['CE'] + side_lots['PE']
    net = np.zeros(4)
    for k, L_ in book.lots.items():
        if not L_: continue
        kk = k2i[k]; p = sum(x['sgn'] for x in L_) * lot
        net += p * np.array([P['gD'][kk, i], P['gG'][kk, i], P['gV'][kk, i], P['gT'][kk, i]])
    mh = book.mtm_hist
    allS = [x for v in book.sale_mi.values() for x in v]; allB = [x for v in book.bb_mi.values() for x in v]
    bm = dict(day=int(m['day'][i]), tte_min=P['T'][i] * 525600, hhmm=P['hh'][i], clockB=bool(P['clockB'][i]), gridA=bool(P['gridA'][i]), grid00=bool(P['grid00'][i]),
              n_contracts=len(sc), lots_ce=side_lots['CE'], lots_pe=side_lots['PE'], lots_tot=tot, imbalance=(side_lots['CE'] - side_lots['PE']) / tot if tot else np.nan,
              max_share=max(len(s) for s in sc.values()) / tot if tot else np.nan, up_ce=side_up['CE'], up_pe=side_up['PE'], up_basket=side_up['CE'] + side_up['PE'],
              mtm=mh[i - 1], mtm_peak=max(mh[:i]), mtm_dd=mh[i - 1] - max(mh[:i]), net_delta=net[0], net_gamma=net[1], net_vega=net[2], net_theta=net[3],
              atr=P['atr'][i], mv1=P['mv1'][i], mv5=P['mv5'][i], mv15=P['mv15'][i], mv30=P['mv30'][i], mv_d0open=P['sd0'][i], mv_prevclose=P['spc'][i], rv1=m['rv1'][i],
              since_sale=last_before(allS, i), since_bb=last_before(allB, i))
    rows = []
    for k, s in sc.items():
        kk = k2i[k]; px = P['mark'][kk, i]
        if not np.isfinite(px): continue
        ents = np.array([x['px'] for x in s]); emi = np.array([x['mi'] for x in s]); cnt = len(s)
        ch = ents.min(); cj = np.where(ents == ch)[0]; ch_mi = emi[cj].min()
        sg = 1 if k[0] == 'CE' else -1; atr = P['atr'][i]; Sp = P['Sp'][i]
        pc = float(m['Cf'][kk, d0 - 1]) if (d0 is not None and d0 > 0) else np.nan
        hp = P['Hp'][kk, i]
        rows.append(dict(cp=k[0], strike=k[1], n_lots=cnt, n_carried=sum(x['carried'] for x in s) if (d0 is not None and i >= d0) else 0, n_reentry=sum(x['reentry'] for x in s),
                         e_cheap=ch, e_avg=ents.mean(), px=px, r_cheap=px / ch, r_avg=px / ents.mean(), rh_prev=hp / ch if np.isfinite(hp) else np.nan,
                         r_prevclose=(px / pc) if (d0 is not None and d0 > 0 and i >= d0 and np.isfinite(pc) and pc > 0) else np.nan,
                         age_cheap=i - ch_mi, age_oldest=i - emi.min(), age_newest=i - emi.max(), upnl=up[k], upnl_side=side_up[k[0]], share_side=cnt / side_lots[k[0]],
                         delta=P['gD'][kk, i], gamma=P['gG'][kk, i], vega=P['gV'][kk, i], theta=P['gT'][kk, i], iv=P['iv'][kk, i],
                         dexp=abs(P['gD'][kk, i]) * cnt * lot, gexp=P['gG'][kk, i] * cnt * lot, vexp=P['gV'][kk, i] * cnt * lot,
                         otm_atr=sg * (P['K'][kk] - Sp) / atr if atr > 0 else np.nan, otm_pts=sg * (P['K'][kk] - Sp),
                         adv_mv5=sg * P['mv5'][i], adv_mv15=sg * P['mv15'][i], adv_mv30=sg * P['mv30'][i], adv_d0open=sg * P['sd0'][i], adv_prevclose=sg * P['spc'][i],
                         since_sale_k=last_before(book.sale_mi.get(k, []), i), since_bb_k=last_before(book.bb_mi.get(k, []), i),
                         tte_min=bm['tte_min'], clockB=bm['clockB'], gridA=bm['gridA'], grid00=bm['grid00'], hhmm=bm['hhmm'], day=bm['day']))
    return rows, bm

# ---------------------------------------------------------------- exogenous stream and DEV-learned rules
def exogenous(o):
    """actual opening orders that are NOT re-entries (sale on a side within 60 s after a short buy-back on that side, plus its wings within 10 s),
    plus all v_ orders.  Platform/manual orders excluded."""
    o = o.copy(); o['t_dec'] = pd.to_datetime(o.t_dec)
    plat = o.algoid.isin(PLATFORM_IDS) | (o.tp == 'm_')
    opening = (o.label == 'open') & ~plat
    bb = o[o.closing_short == True]
    re_ids = set()
    for (u, e, cp), g in o[opening & (o.side == 'Sell') & (o.tp == 'num')].groupby(['und', 'expiry', 'cp']):
        tb = bb[(bb.und == u) & (bb.expiry == e) & (bb.cp == cp)].t_dec.values
        if not len(tb): continue
        for r in g.itertuples():
            d = (r.t_dec - pd.to_datetime(tb)).total_seconds()
            if np.any((d >= 0) & (d <= 60)): re_ids.add(r.oid)
    rs = o[o.oid.isin(re_ids)]
    wing_ids = set()
    for r in rs.itertuples():
        w = o[opening & (o.und == r.und) & (o.expiry == r.expiry) & (o.cp == r.cp) & (o.side == 'Buy') & (o.tp == 'h_')]
        d = (w.t_dec - r.t_dec).dt.total_seconds(); wing_ids |= set(w[(d >= -2) & (d <= 10)].oid)
    exo = o[(opening & ~o.oid.isin(re_ids | wing_ids)) | ((o.tp == 'v_') & ~plat)]
    return exo, re_ids, wing_ids

def dev_rules(o, mk):
    """wing-release ratio, re-entry |delta| target, re-entry lot ratio, wing ratio and premium fraction - all from DEV only"""
    d = o[o.split == 'DEV'].copy(); d['t_dec'] = pd.to_datetime(d.t_dec)
    unsched = d[(d.closing_short == True) & ~d.label.isin(SCHEDULED)]
    rel = d[d.label.str.startswith('L-hedge release')]
    rho = rel.lots.sum() / unsched.lots.sum()
    exo, re_ids, wing_ids = exogenous(d)
    rs = d[d.oid.isin(re_ids)]; dl = []; lr = []
    for r in rs.itertuples():
        m = mk[(r.und, r.expiry)]; P = prepare(m); i = minute_index(m['grid'], r.t_dec_lo); kk = m['k2i'].get((r.cp, r.strike))
        if kk is not None and i > 0: dl.append(abs(P['DELraw'][kk, i - 1]))
    ws = d[d.oid.isin(wing_ids)]
    wl = ws.lots.sum() / max(rs.lots.sum(), 1)
    wfrac = np.median([w.vwap / r.vwap for r in rs.itertuples() for w in ws[(ws.und == r.und) & (ws.expiry == r.expiry) & (ws.cp == r.cp) &
                       ((ws.t_dec - r.t_dec).dt.total_seconds().abs() <= 10)].itertuples()] or [0.025])
    return dict(rho=rho, delta_target=float(np.nanmedian(dl)) if dl else 0.5, wing_lots_per_lot=wl, wing_prem_frac=wfrac)

# ---------------------------------------------------------------- controller models (DEV fit, VAL threshold)
def train_controller(CM, BM, o):
    CMb = CM.merge(BM[['und', 'expiry', 'mi'] + BOOK_JOIN], on=['und', 'expiry', 'mi'], how='left')
    CMb['y_exit'] = (CMb.closed > 0) & (CMb.close_label != '10 manual / platform risk engine')
    X = prep(CMb); feats = [f for f in feats_of(X) if not f.startswith('y_')]
    dev, val = X[X.split == 'DEV'], X[X.split == 'VAL']
    ex = lgb.LGBMClassifier(n_estimators=2000, learning_rate=0.03, num_leaves=31, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1,
                            random_state=0).fit(dev[feats].astype(float), dev.y_exit, eval_set=[(val[feats].astype(float), val.y_exit)], eval_metric='average_precision',
                                                callbacks=[lgb.early_stopping(100, verbose=False)])
    thr = best_threshold(val.y_exit.astype(int).values, ex.predict_proba(val[feats].astype(float))[:, 1])
    def qcls(D): return np.where(D.closed >= D.n_lots, 0, np.where(D.closed == 1, 1, 2))
    ed, ev = dev[dev.y_exit], val[val.y_exit]
    part_frac = float((ed.closed / ed.n_lots)[qcls(ed) == 2].median())
    qm = lgb.LGBMClassifier(objective='multiclass', n_estimators=1000, learning_rate=0.03, num_leaves=15, min_child_samples=20, verbose=-1, random_state=0).fit(
        ed[feats].astype(float), qcls(ed), eval_set=[(ev[feats].astype(float), qcls(ev))], callbacks=[lgb.early_stopping(50, verbose=False)])
    imp = pd.Series(ex.booster_.feature_importance('gain'), index=feats).sort_values(ascending=False)
    top = list(imp.index[:10]); lo = dev[top].astype(float).quantile(0.001); hi = dev[top].astype(float).quantile(0.999)
    # final liquidation (book-minute, D0 >= 14:45)
    FL = BM[(BM.day == 1) & (BM.hhmm >= 14 * 60 + 45) & (BM.n_contracts >= 1)].copy(); FL['y'] = FL.bb_labels.str.contains('final flatten')
    FLp = prep(FL); ff = [f for f in feats_of(FLp) if not f.startswith('y_')]
    fd, fv = FLp[FLp.split == 'DEV'], FLp[FLp.split == 'VAL']
    fm = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.03, num_leaves=7, min_child_samples=20, verbose=-1, random_state=0).fit(fd[ff].astype(float), fd.y.astype(int))
    fthr = best_threshold(fv.y.astype(int).values, fm.predict_proba(fv[ff].astype(float))[:, 1])
    # re-entry (episode-level): book state at the episode minute + episode descriptors
    E, _ = episodes(); E = E[~E.scheduled]
    RE = E.merge(BM, on=['und', 'expiry', 'mi'], how='inner', suffixes=('_ep', ''))
    RE['ep_lots'] = RE.lots; RE['ep_contracts'] = RE.n_contracts_ep; RE['ep_both'] = RE.both_sides.astype(float)
    rf = ['ep_lots', 'ep_contracts', 'ep_both', 'day', 'hhmm', 'clockB', 'gridA', 'grid00', 'tte_min', 'n_contracts', 'lots_tot', 'lots_ce', 'lots_pe', 'mtm', 'mtm_dd', 'mv5', 'mv15', 'atr', 'since_sale', 'since_bb']
    RE[rf] = RE[rf].astype(float)
    rd, rv = RE[RE.split_ep == 'DEV'], RE[RE.split_ep == 'VAL']
    rm = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=7, min_child_samples=20, verbose=-1, random_state=0).fit(rd[rf], rd.rebalance_with_replacement.astype(int))
    rthr = best_threshold(rv.rebalance_with_replacement.astype(int).values, rm.predict_proba(rv[rf])[:, 1])
    return dict(exit=ex, thr=thr, feats=feats, qty=qm, part_frac=part_frac, top=top, lo=lo, hi=hi, final=fm, final_feats=ff, final_thr=fthr, re=rm, re_feats=rf, re_thr=rthr)

# ---------------------------------------------------------------- one cycle
def auto_entries(book, m, i, P, mode):
    """mode B: the decoded clone's entry rules (engine.py): ladder lots per leg at its clock, ATM strike from the previous close,
    one wing per lot at the nearest OTM strike whose previous close <= 1.2 % x straddle premium.  Fills: minute open (or previous close)."""
    sched = {}
    for d, L_ in ((0, LADDER_D1), (1, LADDER_D0)):
        for hm, nl in L_: sched[(d, hm)] = sched.get((d, hm), 0) + nl
    hm = m['grid'][i].strftime('%H:%M'); nl = sched.get((int(m['day'][i]), hm), 0)
    if not nl or i == 0: return
    step = STEP[m['und']]; K = round(m['S'][i - 1] / step) * step; k2i = m['k2i']
    kc, kp = k2i.get(('CE', K)), k2i.get(('PE', K))
    if kc is None or kp is None or not np.isfinite(m['Cf'][kc, i - 1]) or not np.isfinite(m['Cf'][kp, i - 1]): return
    budget = WING_FRAC * (float(m['Cf'][kc, i - 1]) + float(m['Cf'][kp, i - 1]))
    for cp, kk, sg in (('CE', kc, 1), ('PE', kp, -1)):
        book.apply((cp, K), -1, nl, fill_px(m, kk, i, -1, 'open'), i, 'auto entry')
        cand = sorted([k for c, k in m['keys'] if c == cp and (k - K) * sg > 0], key=lambda k: abs(k - K))
        for k in cand:
            v = m['Cf'][k2i[(cp, k)], i - 1]
            if np.isfinite(v) and v <= budget:
                book.apply((cp, k), 1, nl, fill_px(m, k2i[(cp, k)], i, 1, 'open'), i, 'auto wing'); break

def run_cycle(m, exo_c, ctrl, rules, mode='open', policy='model', teacher=None, entries='actual'):
    """entries: 'actual' (mode A: actual base opening orders arrive at their own time) | 'auto' (mode B: decoded clone entry rules)"""
    """policy: 'model' (autonomous), 'hold' (only cycle-stop rule + expiry settlement), 'clone' (1.55x own-entry lot stop at the minute high +
    cycle stop + 15:14 flatten), 'teacher' (apply the given actual orders exactly; used to validate accounting/features)"""
    P = prepare(m); n = len(m['grid']); book = Book(m); lot = book.lot; k2i = m['k2i']; d0 = P['d0']
    exo_by = {}
    src = teacher if policy == 'teacher' else exo_c
    for r in src.itertuples(): exo_by.setdefault(minute_index(m['grid'], r.t_dec_lo), []).append(r)
    stopped = False; abst = 0; decisions = 0; pos_path = np.zeros((len(m['keys']), n)); mtm_path = np.full(n, np.nan); greek_path = np.zeros((n, 4)); fe_rows = []
    for i in range(n):
        if d0 is not None and i == d0: book.mark_carried()
        book.mtm_hist.append(book.mtm_now(i, P) if i > 0 else 0.0)
        for k, L_ in book.lots.items():
            if L_: pos_path[k2i[k], i] = sum(x['sgn'] for x in L_)
        mtm_path[i] = book.mtm_hist[-1]
        if i == 0 or stopped:
            if not stopped and entries == 'actual':
                for r in exo_by.get(i, []): book.apply((r.cp, r.strike), 1 if r.side == 'Buy' else -1, int(r.lots), r.vwap, i, 'exo' if policy != 'teacher' else 'actual')
            continue
        rows, bm = features(book, i, P)
        greek_path[i] = [bm['net_delta'], bm['net_gamma'], bm['net_vega'], bm['net_theta']]
        if policy == 'teacher':
            fe_rows += [dict(r, mi=i, **{f'b_{k}': v for k, v in bm.items()}) for r in rows]
            for r in exo_by.get(i, []): book.apply((r.cp, r.strike), 1 if r.side == 'Buy' else -1, int(r.lots), r.vwap, i, 'actual')
            continue
        # 1 cycle liquidation (fresh close-based MTM at the start of minute i)
        if book.mtm_now(i, P) <= -CYCLE_STOP:
            for k, L_ in list(book.lots.items()):
                p = sum(x['sgn'] for x in L_)
                if p: book.apply(k, -np.sign(p), abs(p), fill_px(m, k2i[k], i, -np.sign(p), mode), i, 'cycle stop')
            stopped = True; continue
        # 2 final liquidation
        if policy == 'model' and bm['day'] == 1 and bm['hhmm'] >= 14 * 60 + 45 and rows:
            fx = prep(pd.DataFrame([dict(bm, und=m['und'], expiry=m['expiry'], split='')]))
            if ctrl['final'].predict_proba(fx[ctrl['final_feats']].astype(float))[:, 1][0] >= ctrl['final_thr']:
                for k, L_ in list(book.lots.items()):
                    p = sum(x['sgn'] for x in L_)
                    if p: book.apply(k, -np.sign(p), abs(p), fill_px(m, k2i[k], i, -np.sign(p), mode), i, 'final flatten')
                stopped = True; continue
        if policy == 'clone' and bm['day'] == 1 and bm['hhmm'] >= 15 * 60 + 14:
            for k, L_ in list(book.lots.items()):
                p = sum(x['sgn'] for x in L_)
                if p: book.apply(k, -np.sign(p), abs(p), fill_px(m, k2i[k], i, -np.sign(p), mode), i, 'final flatten')
            stopped = True; continue
        # 3 contract exits
        bb_side = {'CE': 0, 'PE': 0}; ep_contracts = 0
        if policy == 'model' and rows:
            D = pd.DataFrame(rows); D['und'] = m['und']; D['expiry'] = m['expiry']
            for kb, v in bm.items():
                if kb in BOOK_JOIN: D[kb] = v
            X = prep(D)
            for f in ctrl['feats']:
                if f not in X: X[f] = np.nan
            Xf = X[ctrl['feats']].astype(float)
            p = ctrl['exit'].predict_proba(Xf)[:, 1]; decisions += len(D)
            outside = ((Xf[ctrl['top']] < ctrl['lo']) | (Xf[ctrl['top']] > ctrl['hi'])).any(axis=1).values
            fire = (p >= ctrl['thr']) & ~outside; abst += int(((p >= ctrl['thr']) & outside).sum())
            if fire.any():
                q = ctrl['qty'].predict(Xf[fire]).astype(int)
                for (r, qc) in zip(D[fire].itertuples(), q):
                    nl = int(r.n_lots); nclose = nl if qc == 0 else (1 if qc == 1 else max(1, min(nl, int(round(ctrl['part_frac'] * nl)))))
                    k = (r.cp, r.strike); book.apply(k, 1, nclose, fill_px(m, k2i[k], i, 1, mode), i, 'model exit'); bb_side[r.cp] += nclose; ep_contracts += 1
        elif policy == 'clone':
            for k, L_ in list(book.lots.items()):
                s = [x for x in L_ if x['sgn'] < 0]
                if not s: continue
                kk = k2i[k]; hi = m['H'][kk, i]
                if not np.isfinite(hi): continue
                hit = [x for x in s if hi >= 1.55 * x['px']]
                if hit:
                    lvl = 1.55 * min(x['px'] for x in hit); px = max(float(m['O'][kk, i]), lvl) if np.isfinite(m['O'][kk, i]) else lvl
                    book.apply(k, 1, len(hit), px, i, 'clone lot stop'); bb_side[k[0]] += len(hit)
        # 4 wing release + long salvage
        if policy in ('model', 'clone'):
            for cp, nb in bb_side.items():
                if not nb: continue
                want = int(round(rules['rho'] * nb))
                longs = sorted([(k, sum(x['sgn'] for x in L_)) for k, L_ in book.lots.items() if k[0] == cp and sum(x['sgn'] for x in L_) > 0], key=lambda z: -z[1])
                for k, pl in longs:
                    if want <= 0: break
                    t = min(want, pl); book.apply(k, -1, t, fill_px(m, k2i[k], i, -1, mode), i, 'wing release'); want -= t
            if bm['day'] == 1:
                for k, L_ in list(book.lots.items()):
                    pl = sum(x['sgn'] for x in L_)
                    if pl > 0 and np.isfinite(P['mark'][k2i[k], i]) and P['mark'][k2i[k], i] <= 1.0:
                        book.apply(k, -1, pl, fill_px(m, k2i[k], i, -1, mode), i, 'long salvage')
        # 5 re-entry
        if policy == 'model' and ep_contracts:
            z = dict(ep_lots=sum(bb_side.values()), ep_contracts=ep_contracts, ep_both=float(bb_side['CE'] > 0 and bb_side['PE'] > 0))
            z.update({k_: bm[k_] for k_ in ctrl['re_feats'] if k_ in bm})
            pr = ctrl['re'].predict_proba(pd.DataFrame([z])[ctrl['re_feats']].astype(float))[:, 1][0]
            if pr >= ctrl['re_thr']:
                for cp, nb in bb_side.items():
                    if not nb: continue
                    cand = [(abs(abs(P['DELraw'][kk, i - 1]) - rules['delta_target']), kk) for kk, k in enumerate(m['keys']) if k[0] == cp and np.isfinite(P['mark'][kk, i]) and P['mark'][kk, i] > 1]
                    if not cand: abst += 1; continue
                    kk = min(cand)[1]; k = m['keys'][kk]; spx = fill_px(m, kk, i, -1, mode)
                    book.apply(k, -1, nb, spx, i, 're-entry')
                    wl = int(round(rules['wing_lots_per_lot'] * nb)); budget = rules['wing_prem_frac'] * spx
                    sg = 1 if cp == 'CE' else -1
                    wc = sorted([(abs(P['K'][j] - P['K'][kk]), j) for j, kj in enumerate(m['keys']) if kj[0] == cp and (P['K'][j] - P['K'][kk]) * sg > 0 and np.isfinite(P['mark'][j, i]) and P['mark'][j, i] <= budget])
                    if wl and wc:
                        j = wc[0][1]; book.apply(m['keys'][j], 1, wl, fill_px(m, j, i, 1, mode), i, 're-entry wing')
        # entries of this minute: mode A = actual base opening orders (exogenous); mode B = decoded clone entry rules
        if entries == 'auto': auto_entries(book, m, i, P, mode)
        else:
            for r in exo_by.get(i, []): book.apply((r.cp, r.strike), 1 if r.side == 'Buy' else -1, int(r.lots), r.vwap, i, 'exo')
    # settle at expiry intrinsic (or at the last mark if the cycle is cut before the expiry close)
    settle = m['S'][-1]; pnl = book.realised
    for k, L_ in book.lots.items():
        for x in L_:
            intr = max(settle - k[1], 0) if k[0] == 'CE' else max(k[1] - settle, 0)
            pnl += x['sgn'] * (intr - x['px']) * lot
    return dict(book=book, pnl=pnl, pos=pos_path, mtm=mtm_path, greeks=greek_path, abstained=abst, decisions=decisions, fe=fe_rows)

# ---------------------------------------------------------------- comparison
def compare(m, A, R):
    """A = teacher-forced actual run, R = replay run"""
    keys = m['keys']; isce = prepare(m)['isce']; n = A['pos'].shape[1]
    live = np.where(np.isfinite(A['mtm']) & (np.abs(A['pos']).sum(0) + np.abs(R['pos']).sum(0) > 0))[0]
    if not len(live): return {}
    pa, pr = A['pos'][:, live], R['pos'][:, live]
    div = np.abs(pa - pr).sum(0) / np.maximum(np.abs(pa).sum(0), 1)
    sa = lambda Pm, side: -np.clip(Pm[isce == side], None, 0).sum(0)
    ce_a, ce_r, pe_a, pe_r = sa(pa, True), sa(pr, True), sa(pa, False), sa(pr, False)
    def corr(a, b): return float(np.corrcoef(a, b)[0, 1]) if np.std(a) > 0 and np.std(b) > 0 else np.nan
    out = dict(position_divergence_mean=float(div.mean()), position_divergence_end=float(div[-1]), ce_short_lots_mae=float(np.abs(ce_a - ce_r).mean()), pe_short_lots_mae=float(np.abs(pe_a - pe_r).mean()),
               ce_short_lots_corr=corr(ce_a, ce_r), pe_short_lots_corr=corr(pe_a, pe_r))
    for j, g in enumerate(['delta', 'gamma', 'vega', 'theta']):
        out[f'{g}_corr'] = corr(A['greeks'][live, j], R['greeks'][live, j]); out[f'{g}_mae'] = float(np.abs(A['greeks'][live, j] - R['greeks'][live, j]).mean())
    # exit-event matching: (contract, minute) short buy-backs within +-2 min
    ea = [(o_[1], o_[0], o_[3]) for o_ in A['book'].orders if o_[2] > 0 and o_[5] == 'actual']
    ea = [(k, mi, nl) for k, mi, nl in ea if A['pos'][m['k2i'][k], mi] < 0]
    er = [(o_[1], o_[0], o_[3]) for o_ in R['book'].orders if o_[2] > 0 and o_[5] in ('model exit', 'cycle stop', 'final flatten', 'clone lot stop') and R['pos'][m['k2i'][o_[1]], o_[0]] < 0]
    used = set(); tp = 0; qty_ok = 0; dts = []
    for k, mi, nl in er:
        best = None
        for j, (ka, ma, na) in enumerate(ea):
            if j in used or ka != k or abs(ma - mi) > 2: continue
            if best is None or abs(ma - mi) < abs(ea[best][1] - mi): best = j
        if best is not None: used.add(best); tp += 1; qty_ok += int(ea[best][2] == nl); dts.append(mi - ea[best][1])
    out.update(exit_events_actual=len(ea), exit_events_replay=len(er), exit_match_precision=tp / len(er) if er else np.nan, exit_match_recall=tp / len(ea) if ea else np.nan,
               exit_qty_agreement=qty_ok / tp if tp else np.nan, exit_time_offset_median_min=float(np.median(dts)) if dts else np.nan)
    def mdd(x): x = x[np.isfinite(x)]; return float((x - np.maximum.accumulate(x)).min()) if len(x) else np.nan
    out.update(pnl_actual=A['pnl'], pnl_replay=R['pnl'], mdd_actual=mdd(A['mtm']), mdd_replay=mdd(R['mtm']), turnover_actual=A['book'].turnover, turnover_replay=R['book'].turnover,
               orders_actual=A['book'].n_orders, orders_replay=R['book'].n_orders, units_actual=A['book'].units, units_replay=R['book'].units, abstained=R['abstained'], decisions=R['decisions'])
    for sc, (a, b, c) in COSTS.items():
        out[f'cost_{sc}_actual'] = a * A['book'].turnover + b * A['book'].n_orders + c * A['book'].units
        out[f'cost_{sc}_replay'] = a * R['book'].turnover + b * R['book'].n_orders + c * R['book'].units
    return out

def actual_orders(o, u, e):
    oc = o[(o.und == u) & (o.expiry == e)].copy()
    return oc

def main(mode='open', policies=('model', 'hold', 'clone'), entry_modes=('actual', 'auto')):
    o = orders(); mk = markets(); CM, BM = bookstate.load()
    ctrl = train_controller(CM, BM, o); rules = dev_rules(o, mk)
    exo, _, _ = exogenous(o)
    rows = []
    for (u, e), m in mk.items():
        A = run_cycle(m, None, ctrl, rules, mode, 'teacher', teacher=actual_orders(o, u, e))
        for em in entry_modes:
            for pol in policies:
                R = run_cycle(m, exo[(exo.und == u) & (exo.expiry == e)], ctrl, rules, mode, pol, entries=em)
                r = compare(m, A, R); r.update(und=u, expiry=e, split=split_of(e), policy=pol, fill=mode,
                                               replay_mode='A actual entries + replayed exits' if em == 'actual' else 'B decoded entries + replayed exits'); rows.append(r)
        print(u, e.date(), split_of(e), 'actual', round(A['pnl'] / 1e5, 2), {(rr['replay_mode'][0], rr['policy']): round(rr['pnl_replay'] / 1e5, 2) for rr in rows[-len(policies) * len(entry_modes):]}, flush=True)
    return pd.DataFrame(rows), ctrl, rules

def summarise(D):
    num = [c for c in D.columns if D[c].dtype != object and c not in ('expiry',)]
    out = []
    for (rm, pol, fill, sp), g in D.groupby(['replay_mode', 'policy', 'fill', 'split']):
        r = dict(replay_mode=rm, policy=pol, fill=fill, split=sp, cycles=len(g))
        for c in ['position_divergence_mean', 'position_divergence_end', 'ce_short_lots_corr', 'pe_short_lots_corr', 'ce_short_lots_mae', 'pe_short_lots_mae',
                  'delta_corr', 'gamma_corr', 'vega_corr', 'theta_corr', 'exit_match_precision', 'exit_match_recall', 'exit_qty_agreement', 'exit_time_offset_median_min']:
            if c in g: r[c] = g[c].mean()
        r['pnl_actual_sum_L'] = g.pnl_actual.sum() / 1e5; r['pnl_replay_sum_L'] = g.pnl_replay.sum() / 1e5
        r['pnl_cycle_corr'] = float(np.corrcoef(g.pnl_actual, g.pnl_replay)[0, 1]) if len(g) > 2 and g.pnl_replay.std() > 0 else np.nan
        r['pnl_cycle_mae_L'] = (g.pnl_actual - g.pnl_replay).abs().mean() / 1e5
        r['mdd_actual_mean_L'] = g.mdd_actual.mean() / 1e5; r['mdd_replay_mean_L'] = g.mdd_replay.mean() / 1e5
        r['turnover_ratio'] = g.turnover_replay.sum() / g.turnover_actual.sum(); r['orders_ratio'] = g.orders_replay.sum() / g.orders_actual.sum()
        for sc in COSTS: r[f'net_{sc}_replay_L'] = (g.pnl_replay - g[f'cost_{sc}_replay']).sum() / 1e5; r[f'net_{sc}_actual_L'] = (g.pnl_actual - g[f'cost_{sc}_actual']).sum() / 1e5
        r['abstained'] = g.abstained.sum(); r['abstain_rate'] = g.abstained.sum() / max(g.decisions.sum(), 1)
        out.append(r)
    return pd.DataFrame(out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--fill', default='open'); a = ap.parse_args()
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
    D, ctrl, rules = main(a.fill)
    D.to_csv(os.path.join(RES, f'autonomous_replay_by_cycle_{a.fill}.csv'), index=False)
    S = summarise(D)
    S.to_csv(os.path.join(RES, f'autonomous_replay_metrics_{a.fill}.csv'), index=False)      # merged by run_all.py into autonomous_replay_metrics.csv
    print('rules (DEV):', {k: round(v, 4) for k, v in rules.items()}, '| thresholds exit/final/re-entry:', round(ctrl['thr'], 4), round(ctrl['final_thr'], 4), round(ctrl['re_thr'], 4))
    print(S[S.fill == a.fill].round(3).T.to_string())
