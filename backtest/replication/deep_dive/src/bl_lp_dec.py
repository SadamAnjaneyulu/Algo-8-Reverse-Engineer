"""Lump study step 1 (descriptive): group v_ orders into decisions (same right, within 3 s; chunks of the exchange freeze quantity: NIFTY 27 lots, SENSEX 50 lots), main decision = largest per cycle, others = top-ups.
At each decision: contract-level book on both rights (all modules, orders with te < decision), spot, ATM same-right price, lump strike/price; heavy-side shorts by moneyness; premium value of shorts; intrinsic loss at the lump strike; day's move; clock.
Outputs bl_lp_dec.csv (one row per decision), bl_lp_book.pkl.gz (per-decision book per strike)"""
import sys, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_ohlc, bl_sd_build
CY = pd.read_csv(f'{OUT}/bl_size_cycles.csv'); O = load_orders(); OH = bl_ohlc.load(); OP = bl_sd_build.load_opt(); d1 = O[O.dayno == 0]; rows = []; books = {}
for i, r in enumerate(CY.itertuples()):
    z = d1[(d1.und == r.und) & (d1.expiry == r.expiry)].sort_values(['te', 'row']); v = z[z.module == 'v_'].sort_values('te')
    if not len(v): continue
    o = OH[(r.und, r.expiry)]; h, l, c, op_ = o.high.values, o.low.values, o.close.values, o.open.values; op = OP[(r.und, r.expiry)]; K = op['K']; st = ref.STEP[r.und]
    dec = []; cur = None
    for q in v.itertuples():
        if cur and q.cp == cur['cp'] and q.te - cur['t1'] <= 3: cur['lots'] += q.lots; cur['t1'] = q.te; cur['n'] += 1; cur['rs'] += q.lots * q.px_avg; cur['strikes'].add(q.strike)
        else:
            cur = dict(cp=q.cp, t0=q.te, t1=q.te, lots=q.lots, n=1, rs=q.lots * q.px_avg, strikes={q.strike}, strike=q.strike); dec.append(cur)
    big = max(range(len(dec)), key=lambda x: dec[x]['lots'])
    for di, d in enumerate(dec):
        t = d['t0']; zz = z[z.te < t]; pos = {}
        for q in zz.itertuples(): k = (q.cp, float(q.strike)); pos[k] = pos.get(k, 0) + (1 if q.side.lower() == 'buy' else -1) * q.lots
        j = min(int((t - 33300) // 60), 374); S = c[j - 1]; sg = 1 if d['cp'] == 'CE' else -1
        def px(cp, k):
            w = np.where(np.abs(K - k) < 1)[0]; return op[(cp, 'close')][w[0], j - 1] if len(w) else np.nan
        bk = {cp: sorted([(k, n) for (c2, k), n in pos.items() if c2 == cp and n != 0]) for cp in ('CE', 'PE')}; books[(i, di)] = bk
        sh = [(k, -n) for k, n in bk[d['cp']] if n < 0]; lg = [(k, n) for k, n in bk[d['cp']] if n > 0]; oth = 'PE' if d['cp'] == 'CE' else 'CE'
        S_h = sum(n for _, n in sh); S_o = -sum(n for _, n in bk[oth] if n < 0); KL = d['strike']
        itm = sum(n for k, n in sh if sg * (S - k) > 0); mny = lambda x: sum(n for k, n in sh if abs(k - S) <= x * S / 100)
        loss_KL = sum(n * max(0.0, sg * (KL - k)) for k, n in sh) - sum(n * max(0.0, sg * (KL - k)) for k, n in lg)
        prem_sh = sum(n * px(d['cp'], k) for k, n in sh); atm = px(d['cp'], K[np.argmin(np.abs(K - S))])
        move = (S - c[0]) / c[0] * 100; rows.append(dict(cid=i, und=r.und, version=r.version, unit=r.unit, dec=di, main=int(di == big), cp=d['cp'], t=t, hhmmss=f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}', lots=d['lots'], n_orders=d['n'], strike=KL, n_strikes=len(d['strikes']), px=d['rs'] / d['lots'], otm_pct=sg * (KL / S - 1) * 100,
                         spot=S, S_h=S_h, S_o=S_o, L_h=sum(n for _, n in lg), itm_short=itm, sh_within_0p5=mny(0.5), sh_within_1=mny(1), sh_within_1p5=mny(1.5), loss_at_KL_pts=loss_KL, prem_short_h=prem_sh, atm_px=atm, day_move_pct=move, fav_move_pct=-sg * move,
                         n_short_strikes=len(sh), short_center_steps=(np.average([k for k, _ in sh], weights=[n for _, n in sh]) - S) / st * sg if sh else np.nan))
D = pd.DataFrame(rows); D.to_csv(f'{OUT}/bl_lp_dec.csv', index=False); pd.to_pickle(books, f'{OUT}/bl_lp_book.pkl.gz')
pd.set_option('display.width', 260); print(D[D.main == 1][['cid', 'und', 'version', 'hhmmss', 'cp', 'lots', 'S_h', 'S_o', 'itm_short', 'sh_within_0p5', 'sh_within_1', 'loss_at_KL_pts', 'otm_pct', 'px', 'atm_px', 'day_move_pct']].round(2).to_string(index=False))
print(D[D.main == 0][['cid', 'hhmmss', 'cp', 'lots', 'S_h', 'S_o', 'L_h', 'otm_pct']].round(2).to_string(index=False))
