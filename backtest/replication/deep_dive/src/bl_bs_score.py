"""Buy-back second pass, step 2: loss gate (previous close > cheapest entry) AND indicator; state vs first-crossing semantics; thresholds out-of-fold (cycle halves); F1 at contract-minute level with +-1 minute; AUC within the gate; best two-indicator combinations.
Outputs bl_bs_single.csv, bl_bs_combo.csv, bl_summary_bs1.json"""
import sys, warnings, itertools; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
from scipy.stats import rankdata
X = pd.read_pickle(f'{OUT}/bl_bs_panel.pkl.gz').sort_values(['cid', 'cp', 'strike', 'j']).reset_index(drop=True); R = {}
key = (X.cid.values.astype(np.int64) * 10**7 + X.strike.values.astype(np.int64)) * 2 + (X.cp.values == 'CE'); X['key'] = key
prev_same = np.r_[False, (key[1:] == key[:-1]) & (X.j.values[1:] == X.j.values[:-1] + 1)]
y = X.y.values; h = (X.cid.values % 2 == 0); gate = X.gate.values == 1
ys = {}
for k_, j_ in zip(key[y == 1], X.j.values[y == 1]): ys.setdefault(k_, set()).add(j_)
def f1(fire, idx):
    kk = key[idx & fire]; jj = X.j.values[idx & fire]; nf = len(kk); tpf = sum(1 for a, b in zip(kk, jj) if a in ys and (b in ys[a] or b - 1 in ys[a] or b + 1 in ys[a]))
    fs = {}
    for a, b in zip(kk, jj): fs.setdefault(a, set()).add(b)
    yi = idx & (y == 1); tpy = sum(1 for a, b in zip(key[yi], X.j.values[yi]) if a in fs and (b in fs[a] or b - 1 in fs[a] or b + 1 in fs[a])); ny = int(yi.sum())
    p = tpf / max(nf, 1); r = tpy / max(ny, 1); return 2 * p * r / max(p + r, 1e-9), p, r
def cross(cond): pc = np.r_[False, cond[:-1]]; return cond & ~(pc & prev_same)
CONT = ['ratio_c', 'ratio_h', 'loss_pts', 'loss_patr', 'trail_prem', 'adv_steps', 'adv_atr', 'adv_pct', 'chand_atr', 'rsi_against', 'vel3']
BIN = ['st1_against', 'st1_flip', 'st2_against', 'st2_flip', 'psar_against', 'psar_flip', 'don20', 'don60', 'boll', 'ema_against', 'ema_cross']
def auc(s, yy): m = ~np.isnan(s); s, yy = s[m], yy[m]; n1 = yy.sum(); n0 = len(yy) - n1; return (rankdata(s)[yy == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)
rows = []; BEST = {}
for v in CONT:
    s = X[v].values.astype(float); s = np.where(np.isnan(s), -1e9, s); grid = np.unique(np.quantile(s[gate & (s > -1e9)], np.linspace(0.5, 0.995, 60)))
    for sem in ('state', 'cross'):
        mk = (lambda t: gate & (s >= t)) if sem == 'state' else (lambda t: gate & cross(s >= t)); oof = []
        for tr in (h, ~h):
            t = max(grid, key=lambda t: f1(mk(t), tr)[0]); oof.append((t, *f1(mk(t), ~tr)))
        rows.append(dict(indicator=v, semantics=sem, AUC_in_gate=auc(X[v].values[gate].astype(float), y[gate]), thr=f'{oof[0][0]:.3f}/{oof[1][0]:.3f}', F1_half1=oof[0][1], F1_half2=oof[1][1], F1=np.mean([o[1] for o in oof]), precision=np.mean([o[2] for o in oof]), recall=np.mean([o[3] for o in oof])))
        BEST[(v, sem)] = np.mean([o[0] for o in oof])
for v in BIN:
    b = X[v].values == 1
    for sem in ('state', 'cross'):
        fire = gate & (b if sem == 'state' else cross(b)); a1, a2 = f1(fire, h), f1(fire, ~h); rows.append(dict(indicator=v, semantics=sem, AUC_in_gate=auc(X[v].values[gate].astype(float), y[gate]), thr='-', F1_half1=a1[0], F1_half2=a2[0], F1=(a1[0] + a2[0]) / 2, precision=(a1[1] + a2[1]) / 2, recall=(a1[2] + a2[2]) / 2))
a1, a2 = f1(gate, h), f1(gate, ~h); rows.append(dict(indicator='loss gate only', semantics='state', AUC_in_gate=np.nan, thr='-', F1_half1=a1[0], F1_half2=a2[0], F1=(a1[0] + a2[0]) / 2, precision=(a1[1] + a2[1]) / 2, recall=(a1[2] + a2[2]) / 2))
T = pd.DataFrame(rows).sort_values('F1', ascending=False); T.round(4).to_csv(f'{OUT}/bl_bs_single.csv', index=False); print(T.round(3).head(24).to_string(index=False))
# combos: best premium crossing OR/AND each spot indicator (state or crossing), thresholds of the premium part re-fitted out-of-fold
prem = T[T.indicator.isin(['ratio_c', 'ratio_h', 'loss_patr', 'trail_prem', 'loss_pts', 'vel3'])].iloc[0]; pv, psem = prem.indicator, prem.semantics; s = X[pv].values.astype(float); s = np.where(np.isnan(s), -1e9, s)
pgrid = np.unique(np.quantile(s[gate & (s > -1e9)], np.linspace(0.7, 0.995, 30))); cr = []
others = [x for x in CONT if x != pv] + BIN
for ov in others:
    so = X[ov].values.astype(float); so = np.where(np.isnan(so), -1e9, so); ogrid = [0.5] if ov in BIN else np.unique(np.quantile(so[gate & (so > -1e9)], np.linspace(0.6, 0.995, 15)))
    for op_, osem in itertools.product(('OR', 'AND'), ('state', 'cross')):
        def mk(t, u):
            a = (s >= t) if psem == 'state' else cross(s >= t); b = (so >= u) if osem == 'state' else cross(so >= u); return gate & ((a | b) if op_ == 'OR' else (a & b))
        oof = []
        for tr in (h, ~h):
            tu = max(((t, u) for t in pgrid for u in ogrid), key=lambda tu: f1(mk(*tu), tr)[0]); oof.append(f1(mk(*tu), ~tr)[0])
        cr.append(dict(rule=f'{pv} ({psem}) {op_} {ov} ({osem})', F1_half1=oof[0], F1_half2=oof[1], F1=np.mean(oof)))
C = pd.DataFrame(cr).sort_values('F1', ascending=False); C.round(4).to_csv(f'{OUT}/bl_bs_combo.csv', index=False); print(C.head(10).round(3).to_string(index=False))
R['single'] = T.round(4).to_dict('records'); R['combo_top'] = C.head(15).round(4).to_dict('records'); rec('bs1', R)
