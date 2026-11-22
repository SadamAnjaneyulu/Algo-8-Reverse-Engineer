"""Body-sell error breakdown in the free-running reconstruction (stop design from bl_bb_fit, out-of-fold): recall by real sell type (scheduled / reactive / solo intraday / solo after 15:00 / deep-OTM batch) and precision by simulated type (scheduled / reactive / extra / solo ladder). Output bl_sell_err.csv, bl_summary_se1.json"""
import sys, warnings, json; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
src = open('bl_fr_score.py').read(); exec(src[:src.index("CLS_ROWS = []")])
SD = pd.read_pickle(f'{OUT}/bl_sd_orders.pkl.gz'); ch = json.load(open(f'{OUT}/bl_summary_bb6.json'))['chosen']; allo = {}
for h_, c_ in zip((0, 1), ch):
    tr = [i for i in ids if i % 2 == h_]; te = [i for i in ids if i % 2 != h_]; P = fit_params(tr); vel = eval(c_['vel']); P.update(tp=c_['tp'], bb_price=c_['price'], theta=c_['theta'], bb_vel=vel, bb_cluster=c_['cluster'] if c_['cluster'] == c_['cluster'] else None); allo.update(OO(run(te, P, 'free')))
SD['rtyp'] = np.where(SD.deep, 'deep-OTM batch', np.where((SD.typ == 'solo') & (SD.te >= 54000), 'solo after 15:00', np.where(SD.typ == 'solo', 'solo intraday', SD.typ)))
rec_r = {t: [0, 0] for t in SD.rtyp.unique()}; prec_s = {}
for i in ids:
    o = allo[i]; ol = lots_of(o[o.cls == 'body_sell']); z = lots_of(SD[SD.cid == i])
    for cp in ('CE', 'PE'):
        rr = z[z.cp == cp].sort_values('j'); ss = ol[ol.cp == cp]
        # match all real lots to all sim lots, then attribute
        bucket = {}
        for n_, j in enumerate(ss.j.values): bucket.setdefault(int(j), []).append(n_)
        used = np.zeros(len(ss), bool); hit = np.zeros(len(rr), bool)
        for ps in (0, 1):
            for a, j in enumerate(rr.j.values):
                if hit[a]: continue
                for jj in ({j} if ps == 0 else {j - 1, j + 1}):
                    c2 = [n_ for n_ in bucket.get(int(jj), []) if not used[n_]]
                    if c2: used[c2[0]] = True; hit[a] = True; break
        for t, h_ in zip(rr.rtyp.values, hit): rec_r[t][0] += int(h_); rec_r[t][1] += 1
        for t, u in zip(ss.typ.values, used): prec_s.setdefault(t, [0, 0]); prec_s[t][0] += int(u); prec_s[t][1] += 1
A = pd.DataFrame([dict(side='real (recall)', type=t, lots=v[1], matched=v[0], share=v[0] / v[1]) for t, v in rec_r.items()] + [dict(side='simulated (precision)', type=t, lots=v[1], matched=v[0], share=v[0] / v[1]) for t, v in prec_s.items()])
A.round(4).to_csv(f'{OUT}/bl_sell_err.csv', index=False); print(A.round(3).to_string(index=False)); rec('se1', dict(table=A.round(4).to_dict('records')))
