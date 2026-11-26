"""D0 chunk 2, B2 (plan reports/D0_BUYBACKS_PLAN.md): buy-back machines on the real book (real sells; lots leave the book at their real buy-back = 'real' semantics, primary),
fitted on one cycle half (cid parity) and scored on the other. Lot F1 at +-1 minute against real body buy-back lots before 15:10 and the stop (minute histogram matcher).
K1 D-1 stop unchanged (high >= 1.6 x entry); K2 refit theta x price, per hour block, per origin; K3 + take-profit (low <= tp x entry, time gate); K4 + same-strike partner; K5 + block clock.
Secondary: 'own' semantics (lots leave only at the machine's own exits, as a simulator would). Nulls for the final machine: +15 min shift; rate-matched random minutes.
Outputs bl_d0b_mach.csv, bl_d0b_mach_chosen.json, bl_summary_d0b2.json"""
import sys, warnings, json, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
src = open('bl_d0b_tests.py').read(); exec(src[:src.index('# ---------------- B1 panel')])
NJ = 376; rng = np.random.default_rng(5)
def hist(js, w=None):
    a = np.zeros(NJ, int); np.add.at(a, np.clip(np.asarray(js, int), 0, NJ - 1), 1 if w is None else np.asarray(w, int)); return a
def mt(a, p):
    a = a.copy(); p = p.copy(); m = np.minimum(a, p); n = int(m.sum()); a -= m; p -= m
    for j in range(NJ):
        if a[j] == 0: continue
        for jj in (j - 1, j + 1):
            if 0 <= jj < NJ and a[j] and p[jj]: x = min(a[j], p[jj]); a[j] -= x; p[jj] -= x; n += x
    return n
C = {}
for i in D0C:
    r = CY.iloc[i]; op = OPT[(r.und, r.expiry)]; ki = {int(k): x for x, k in enumerate(op['K'])}; L = []
    for l in BK[i]['lots']:
        if l['entry_day'] == 0 and l.get('exit_day', 1) == 0 and l['exit_tod'] == l['exit_tod']: continue
        if l['strike'] not in ki: continue
        j0 = 1 if l['entry_day'] == 0 else int((l['entry_tod'] - 33300) // 60) + 1; jx = int((l['exit_tod'] - 33300) // 60) if (l['exit_tod'] == l['exit_tod'] and l.get('exit_day', 1) == 1) else 999
        L.append((j0, jx, ki[l['strike']], l['entry'], 0 if l['cp'] == 'CE' else 1, l['strike'], 0 if l['entry_day'] == 0 else 1))
    A = np.array(L, float); x = A[:, 2].astype(int); e = A[:, 3]; cpi = A[:, 4].astype(int)
    H = np.where(cpi[:, None] == 0, op[('CE', 'high')][x], op[('PE', 'high')][x]) / e[:, None]; Lo = np.where(cpi[:, None] == 0, op[('CE', 'low')][x], op[('PE', 'low')][x]) / e[:, None]
    Cl = np.where(cpi[:, None] == 0, op[('CE', 'close')][x], op[('PE', 'close')][x]) / e[:, None]; Cp = np.concatenate([Cl[:, :1], Cl[:, :-1]], axis=1)
    xs = XS[XS.cid == i]; C[i] = dict(j0=A[:, 0].astype(int), jx=A[:, 1].astype(int), cp=cpi, k=A[:, 5], org=A[:, 6].astype(int), H=np.nan_to_num(H, nan=0), Lo=np.nan_to_num(Lo, nan=9), Cp=np.nan_to_num(Cp, nan=0), je=JEND[i],
                                     real={cp: hist(xs[xs.cp == cp].j) for cp in ('CE', 'PE')}, realg={(cp, g): hist(xs[(xs.cp == cp) & (xs.grp == g)].j) for cp in ('CE', 'PE') for g in ('loss', 'mid-profit', 'deep-profit')})
JJ = np.arange(375); BLK = ((JJ) % 15); HB = np.digitize(JJ, [105, 225])          # hour blocks 0: <11:00, 1: 11-13, 2: >=13:00
def run(i, P, sem='real'):
    d = C[i]; n = len(d['j0']); je = d['je']; jj = JJ[None, :]; alive = (jj >= d['j0'][:, None]) & (jj <= je)
    if sem == 'real': alive &= jj <= d['jx'][:, None]
    clk = np.isin(BLK, [14, 0])[None, :] if P.get('clock') else True
    th = np.full(375, P['theta'])
    if P.get('theta_blk'): th = np.array(P['theta_blk'])[HB]
    TH = np.where(d['org'][:, None] == 0, th[None, :] * P.get('org_mult', [1, 1])[0], th[None, :] * P.get('org_mult', [1, 1])[1])
    R_ = d['H'][:, :375] if P['price'] == 'high' else d['Cp'][:, :375]; hit = alive & (R_ >= TH) & clk
    first = np.where(hit.any(1), hit.argmax(1), 999); typ = np.zeros(n, int)
    if P.get('tp'):
        tph = alive & (d['Lo'][:, :375] <= P['tp']) & (jj >= P.get('tp_gate', 0)) & clk; ft = np.where(tph.any(1), tph.argmax(1), 999); typ = np.where(ft < first, 1, 0); first = np.minimum(first, ft)
    if P.get('partner'):
        order = np.argsort(first); ex = first.copy()
        for a in order:
            if ex[a] >= 999 or ex[a] != first[a] or typ[a] != 0: continue
            j = ex[a]; cand = np.where((d['cp'] != d['cp'][a]) & (d['k'] == d['k'][a]) & (d['j0'] <= j) & (ex > j) & ((d['jx'] >= j) if sem == 'real' else True))[0]
            if len(cand): b = cand[np.argmax(d['H'][cand, j])]; ex[b] = j; typ[b] = 2
        first = ex
    return {cp: hist(first[(d['cp'] == c) & (first < 999)]) for c, cp in ((0, 'CE'), (1, 'PE'))}
def score(P, cids, sem='real', shift=0, rnd=False):
    tp = ns = nr = 0; per = []; gm = {g: 0 for g in ('loss', 'mid-profit', 'deep-profit')}; gn = {g: 0 for g in gm}
    for i in cids:
        pr = run(i, P, sem); x = [0, 0, 0]
        for cp in ('CE', 'PE'):
            p = pr[cp]
            if shift: p = np.roll(p, shift); p[:shift] = 0
            if rnd: p = hist(rng.integers(1, C[i]['je'] + 1, int(p.sum())))
            a = C[i]['real'][cp]; x[0] += mt(a, p); x[1] += int(p.sum()); x[2] += int(a.sum())
            for g in gm: ag = C[i]['realg'][(cp, g)]; gm[g] += mt(ag, p); gn[g] += int(ag.sum())
        per.append(tuple(x))
    a = np.array(per); f = 2 * a[:, 0].sum() / max(a[:, 1].sum() + a[:, 2].sum(), 1)
    return f, per, {g: gm[g] / max(gn[g], 1) for g in gm}
f1 = lambda P, c, sem='real': score(P, c, sem)[0]
def boot(per, reps=1000):
    a = np.array(per, float); g = lambda x: 2 * x[:, 0].sum() / max(x[:, 1].sum() + x[:, 2].sum(), 1); bs = [g(a[rng.integers(0, len(a), len(a))]) for _ in range(reps)]; return np.percentile(bs, 2.5), np.percentile(bs, 97.5)
TH_ = [round(1.2 + 0.1 * k, 1) for k in range(11)]
def fit(tr):
    steps = {}; P = dict(theta=1.6, price='high'); steps['K1 D-1 stop unchanged (high >= 1.6x)'] = dict(P)
    best = max(itertools.product(TH_, ('high', 'close')), key=lambda c: f1(dict(theta=c[0], price=c[1]), tr)); P = dict(theta=best[0], price=best[1]); steps['K2a refit theta and price'] = dict(P)
    Pb = dict(P, theta_blk=[P['theta']] * 3)
    for _ in range(2):
        for b in range(3):
            def g(t): q = dict(Pb); tb = list(q['theta_blk']); tb[b] = t; q['theta_blk'] = tb; return f1(q, tr)
            t = max(TH_, key=g); tb = list(Pb['theta_blk']); tb[b] = t; Pb['theta_blk'] = tb
    steps['K2b theta per hour block'] = dict(Pb)
    Po = dict(P, org_mult=[1, 1]); mlt = [0.8, 0.9, 1.0, 1.1, 1.2]
    for _ in range(2):
        for o in range(2):
            def g(m): q = dict(Po); om = list(q['org_mult']); om[o] = m; q['org_mult'] = om; return f1(q, tr)
            m = max(mlt, key=g); om = list(Po['org_mult']); om[o] = m; Po['org_mult'] = om
    steps['K2c theta per origin'] = dict(Po)
    base = max((steps['K2a refit theta and price'], Pb, Po), key=lambda q: f1(q, tr))
    best = max(itertools.product((0.1, 0.15, 0.2, 0.25, 0.3, 0.4), (0, 165, 225, 285)), key=lambda c: f1(dict(base, tp=c[0], tp_gate=c[1]), tr)); P3 = dict(base, tp=best[0], tp_gate=best[1])
    if f1(P3, tr) <= f1(base, tr): P3 = dict(base)
    steps['K3 + take-profit'] = dict(P3); P4 = dict(P3, partner=True); P4 = P4 if f1(P4, tr) > f1(P3, tr) else dict(P3); steps['K4 + same-strike partner'] = dict(P4)
    P5 = dict(P4, clock=True); P5 = P5 if f1(P5, tr) > f1(P4, tr) else dict(P4); steps['K5 + block clock'] = dict(P5)
    return steps
rows = []; chosen = {}; PER = {}
FITS = {h: fit([i for i in D0C if i % 2 != h]) for h in (0, 1)}
for nm in FITS[0]:
    per = []; grec = {g: [] for g in ('loss', 'mid-profit', 'deep-profit')}
    for h in (0, 1):
        te = [i for i in D0C if i % 2 == h]; f, p, gr = score(FITS[h][nm], te); per += p
        for g in gr: grec[g].append(gr[g])
    a = np.array(per); lo, hi = boot(per); PER[nm] = per
    rows.append(dict(machine=nm, F1=2 * a[:, 0].sum() / (a[:, 1].sum() + a[:, 2].sum()), ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / a[:, 2].sum(), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum()),
                     recall_loss=np.mean(grec['loss']), recall_mid=np.mean(grec['mid-profit']), recall_deep=np.mean(grec['deep-profit'])))
    chosen[nm] = [json.dumps(FITS[h][nm]) for h in (0, 1)]
fin = 'K5 + block clock'
for lab, kw in (('null: final machine shifted +15 min', dict(shift=15)), ('null: rate-matched random minutes', dict(rnd=True)), ('secondary: final machine, own-book semantics', dict(sem='own'))):
    per = []
    for h in (0, 1): te = [i for i in D0C if i % 2 == h]; per += score(FITS[h][fin], te, **kw)[1]
    a = np.array(per); lo, hi = boot(per); rows.append(dict(machine=lab, F1=2 * a[:, 0].sum() / (a[:, 1].sum() + a[:, 2].sum()), ci_lo=lo, ci_hi=hi, precision=a[:, 0].sum() / max(a[:, 1].sum(), 1), recall=a[:, 0].sum() / a[:, 2].sum(), sim_lots=int(a[:, 1].sum()), real_lots=int(a[:, 2].sum())))
T = pd.DataFrame(rows); T.to_csv(f'{OUT}/bl_d0b_mach.csv', index=False); json.dump(chosen, open(f'{OUT}/bl_d0b_mach_chosen.json', 'w'), indent=1); print(T.round(3).to_string(index=False)); print(json.dumps(chosen, indent=1))
rec('d0b2', dict(F1={r.machine: round(r.F1, 4) for r in T.itertuples()}, chosen=chosen))
