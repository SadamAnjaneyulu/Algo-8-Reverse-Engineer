"""Buy-back study, step 1: replay every order per cycle with a lot tracker (three ownership conventions) and write
  outputs/bl_close_orders.csv   one row per BODY buy-back order (role cover_short): decision-time price (limit/1.15), entry references (avg / cheapest-open = LOW / oldest = FIFO),
                                other-leg state at the same strike, time held, hold, emptying, re-sell within 60 s, pairing flags
  outputs/bl_close_panel2.csv.gz strike-level contract-minute panel (body short lots open): own and other-leg ratios, straddle ratio, event flags (body buy-back in minute j)
  outputs/bl_close_lots.csv     lot-level (D-1 sells): max ratio reached while open, closed on D-1 or carried, per convention FIFO / LOW / HIGH
Lot ownership inside a strike is unobserved: FIFO closes the oldest lot first, LOW the lowest-entry lot first, HIGH the highest-entry lot first. avg = open-average with pro-rata removal."""
import sys, warnings, bisect; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
O = load_orders(); cyc = pd.read_csv(ref.CYCLES); ch = Chain(); LOT = ref.LOT
CONV = ('fifo', 'low', 'high')


class Pos:
    """open body short lots at one (cp, strike). lot = [entry_px, t_entry, maxp, lot_id, sold_day]"""
    def __init__(self): self.L = {c: [] for c in CONV}; self.v = 0.0; self.n = 0
    def add(self, px, t, lid, day, k):
        for _ in range(k):
            for c in CONV: self.L[c].append([px, t, px, lid, day, px])
        self.v += px * k; self.n += k
    def stats(self):
        if self.n <= 0 or not self.L['fifo']: return None
        e = [x[0] for x in self.L['low']]
        return dict(n=self.n, avg=self.v / self.n, low=min(e), fifo=self.L['fifo'][0][0], high=max(e), t_fifo=self.L['fifo'][0][1])
    def remove(self, k, out=None, t=None):
        k = min(k, self.n)
        for _ in range(k):
            avg = self.v / self.n
            for c in CONV:
                L = self.L[c]
                i = 0 if c == 'fifo' else (min(range(len(L)), key=lambda q: L[q][0]) if c == 'low' else max(range(len(L)), key=lambda q: L[q][0]))
                x = L.pop(i)
                if out is not None: out.append((c, x[3], x[0], x[2], t, x[5], x[1]))
            self.v -= avg; self.n -= 1
    def touch(self, p):
        for c in CONV:
            for x in self.L[c]:
                if p > x[2]: x[2] = p
                if p < x[5]: x[5] = p


orows = []; prow = []; lrows = []; lid = 0
for u, e, hd1, hd0 in zip(cyc.und, cyc.expiry, cyc.has_d1, cyc.has_d0):
    c = ch.cyc(u, e); K = np.array(c['strikes'], dtype=float); si = c['_si']; step = ref.STEP[u]
    E = O[(O.und == u) & (O.expiry == e)].sort_values(['te', 'row']); evs = list(E.itertuples()); ptr = 0; pos = {}
    P = {0: {'CE': np.array(c[(0, 'CE', 'close')], dtype=float), 'PE': np.array(c[(0, 'PE', 'close')], dtype=float)}, 1: {'CE': np.array(c[(1, 'CE', 'close')], dtype=float), 'PE': np.array(c[(1, 'PE', 'close')], dtype=float)}}
    spot = {0: np.array(c[(0, 'spot')], dtype=float), 1: np.array(c[(1, 'spot')], dtype=float)}
    sells_body = []  # (te, cp, strike) body open_short sells for the re-sell flag
    for r in evs:
        if r.module == 'num' and r.role == 'open_short': sells_body.append((r.te, r.cp, r.strike))
    sb_te = np.array([x[0] for x in sells_body]); sb_cp = np.array([x[1] for x in sells_body]); sb_k = np.array([x[2] for x in sells_body])

    def apply(r):
        global lid
        key = (r.cp, int(r.strike)); p = pos.setdefault(key, Pos())
        if r.role == 'open_short' and r.module == 'num':
            lid += 1; p.add(float(r.px_avg), r.te, lid, r.dayno, int(r.lots))
        elif r.role == 'cover_short':
            if r.module == 'num':
                st = p.stats(); other = pos.get(('PE' if r.cp == 'CE' else 'CE', int(r.strike))); so = other.stats() if other else None
                j = int(r.jj) if r.jj == r.jj else int((r.tod - ref.OPEN_SEC) // 60); jm = min(max(j - 1, 0), 374); dpx = float(r.ref_px)
                pc = P[r.dayno][r.cp][si.get(int(r.strike), -1), jm] if si.get(int(r.strike)) is not None else np.nan
                po = P[r.dayno]['PE' if r.cp == 'CE' else 'CE'][si[int(r.strike)], jm] if si.get(int(r.strike)) is not None else np.nan
                s0 = spot[r.dayno][jm]; side = 1 if r.cp == 'CE' else -1
                nxt = ((sb_te > r.te) & (sb_te <= r.te + 60)); rs_same = bool(((sb_cp == r.cp) & (sb_k == r.strike) & nxt).any()); rs_any = bool(((sb_cp == r.cp) & nxt).any())
                rs_other = bool(((sb_cp != r.cp) & nxt).any())
                orows.append(dict(und=u, expiry=e, day=['D-1', 'D0'][r.dayno], tag=r.tag, cp=r.cp, strike=int(r.strike), lots=int(r.lots), te=r.te, tod=r.tod, j=j, dec_px=dpx, fill_px=float(r.px_avg), px_chain=pc,
                    n_open=(st['n'] if st else 0), avg=(st['avg'] if st else np.nan), low=(st['low'] if st else np.nan), fifo=(st['fifo'] if st else np.nan), high=(st['high'] if st else np.nan),
                    hold_fifo_min=((r.te - st['t_fifo']) / 60 if st else np.nan), empties=int(bool(st) and st['n'] <= r.lots),
                    o_n_open=(so['n'] if so else 0), o_avg=(so['avg'] if so else np.nan), o_low=(so['low'] if so else np.nan), o_px_chain=po,
                    itm_steps=(side * (s0 - r.strike) / step if s0 == s0 else np.nan), resell_same=int(rs_same), resell_any=int(rs_any), resell_other=int(rs_other)))
            out = [] if r.dayno == 0 else None
            if r.dayno == 0 and p.n > 0: p.remove(int(r.lots), out=out, t=r.te)
            elif p.n > 0: p.remove(int(r.lots))
            if out:
                for (cv, lid_, ent, mp, t, mn, te0) in out: lrows.append((u, e, r.cp, int(r.strike), cv, lid_, ent, mp, t, 1, mn, te0))
    for d, has in ((0, hd1), (1, hd0)):
        if not has: continue
        base = d * 100000
        for j in range(0, 375):
            thr = base + ref.OPEN_SEC + j * 60
            while ptr < len(evs) and evs[ptr].te < thr: apply(evs[ptr]); ptr += 1
            if j < 5 or j > 373: continue
            s1 = spot[d][j - 1]
            if not np.isfinite(s1): continue
            cov = {}
            # body buy-backs inside minute j (orders with first fill in [thr, thr+60))
            k0 = ptr
            while k0 < len(evs) and evs[k0].te < thr + 60:
                q = evs[k0]; k0 += 1
                if q.module == 'num' and q.role == 'cover_short': cov[(q.cp, int(q.strike))] = cov.get((q.cp, int(q.strike)), 0) + int(q.lots)
            for (cp, ks), p in pos.items():
                st = p.stats()
                if st is None: continue
                i = si.get(ks)
                if i is None: continue
                pr = P[d][cp][i, j - 1]
                if not np.isfinite(pr) or st['avg'] <= 0: continue
                p.touch(pr)
                oc = 'PE' if cp == 'CE' else 'CE'; op = pos.get((oc, ks)); so = op.stats() if op else None; po = P[d][oc][i, j - 1]
                side = 1 if cp == 'CE' else -1
                oev = cov.get((oc, ks), 0); anyo = sum(v for (cc, kk), v in cov.items() if cc == oc)
                sr = (pr + po) / (st['avg'] + so['avg']) if (so is not None and np.isfinite(po)) else np.nan
                prow.append((u, e, ['D-1', 'D0'][d], cp, ks, j, cov.get((cp, ks), 0), oev, anyo, pr, st['avg'], st['low'], st['fifo'], st['n'], pr / st['avg'], pr / st['low'], pr / st['fifo'],
                    (so['n'] if so else 0), (po if np.isfinite(po) else np.nan), (so['avg'] if so else np.nan), (po / so['avg'] if (so is not None and np.isfinite(po)) else np.nan), (po / so['low'] if (so is not None and np.isfinite(po)) else np.nan), sr,
                    side * (s1 - ks) / step, (j - 1) - (st['t_fifo'] - base - ref.OPEN_SEC) / 60.0))
        while ptr < len(evs) and evs[ptr].te < base + 100000: apply(evs[ptr]); ptr += 1
        if d == 0:  # lots still open at the end of D-1
            for (cp, ks), p in pos.items():
                for cv in CONV:
                    for x in p.L[cv]:
                        if x[4] == 0: lrows.append((u, e, cp, ks, cv, x[3], x[0], x[2], np.nan, 0, x[5], x[1]))
O2 = pd.DataFrame(orows); O2.to_csv(f'{OUT}/bl_close_orders.csv', index=False)
pc = ['und', 'expiry', 'day', 'cp', 'strike', 'j', 'bb_lots', 'o_bb_lots', 'o_bb_any', 'price', 'avg', 'low', 'fifo', 'n_open', 'r_avg', 'r_low', 'r_fifo', 'o_n_open', 'o_price', 'o_avg', 'o_r_avg', 'o_r_low', 'straddle_r', 'itm_steps', 'hold_min']
Pn = pd.DataFrame(prow, columns=pc); Pn.to_csv(f'{OUT}/bl_close_panel2.csv.gz', index=False)
Ln = pd.DataFrame(lrows, columns=['und', 'expiry', 'cp', 'strike', 'conv', 'lot_id', 'entry', 'maxp', 'closed_te', 'closed_d1', 'minp', 't_entry']); Ln['max_ratio'] = Ln.maxp / Ln.entry; Ln['min_ratio'] = Ln.minp / Ln.entry; Ln.to_csv(f'{OUT}/bl_close_lots.csv', index=False)
print(O2.groupby('day').size(), Pn.groupby('day').agg(rows=('bb_lots', 'size'), ev=('bb_lots', lambda s: (s > 0).sum())), Ln.groupby(['conv', 'closed_d1']).size())
