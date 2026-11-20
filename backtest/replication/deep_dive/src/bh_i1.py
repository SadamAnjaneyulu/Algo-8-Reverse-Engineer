"""I1: event-level timelines for cases selected by pre-registered rules (first instance in cycle order, no cherry-picking). Output outputs/bh_i1_cases.md and outputs/bh_i1_cases_index.csv.
Event time: body orders = first fill second (resolution 1 s); stamped modules = microsecond decision stamp. S/L = contract-level short/long lots of the right after the event."""
import sys; sys.path.insert(0, '.')
from bh_common import *
O = order_table(); O['te'] = np.where(O.module.isin(['h_', 's_', 'v_', 'm_']), O.tt_dec, O.tt_first); O['sl'] = np.where(O.side == 'Buy', O.lots, -O.lots)
BL = pd.read_csv(f'{OUT}/bh_h1_body_lots.csv', dtype={'tag': str, 'wing_tag': str}); G = pd.read_csv(f'{OUT}/bh_h3c_wing_orders.csv', dtype={'tag': str}); A = pd.read_csv(f'{OUT}/bh_h6_bursts.csv'); Q = pd.read_csv(f'{OUT}/bh_h6_quiet.csv')
def hms(t): t = t % 100000; return '%02d:%02d:%06.3f' % (t // 3600, (t % 3600) // 60, t % 60)
def timeline(u, e, cp, d, t_lo, t_hi):
    o = O[(O.und == u) & (O.expiry == e) & (O.cp == cp)].sort_values(['te', 'row']); net = {}; out = []
    for r in o.itertuples():
        net[r.strike] = net.get(r.strike, 0) + r.sl; n = np.array(list(net.values())); S = -n[n < 0].sum(); L = n[n > 0].sum()
        if t_lo <= r.te <= t_hi: out.append((hms(r.te), {'num': 'BODY', 'h_': 'HEDGE'}.get(r.module, r.module), r.side, r.strike, r.lots, r.lim_px, round(r.px_avg, 2), S, L, S - L, r.tag))
    return pd.DataFrame(out, columns=['time(IST)', 'module', 'side', 'strike', 'lots', 'limit', 'fill', 'S_after', 'L_after', 'gap', 'tag'])
cases = []
def add(name, desc, u, e, cp, d, t0, pad_lo=8, pad_hi=25): cases.append((name, desc, u, e, cp, int(d), t0, pad_lo, pad_hi))
c = BL[(BL.matched) & (BL.dayno == 0)].merge(G[['tag', 'gap_before', 'gap_after', 'lots', 'lim_lots', 'complete']], left_on='wing_tag', right_on='tag', suffixes=('', '_w'))
x = c[(c.lag.between(2.5, 6)) & (c.gap_after == 0) & (c.lots == 1) & (c.complete) & (c.side == 'Sell')].sort_values(['und', 'expiry', 'tt']); r = x.iloc[0]; add('normal', 'D-1 body short sale, one wing lot 2.5-6 s later, balance restored', r.und, r.expiry, r.cp, r.dayno, r.tt)
bo = O[(O.module == 'num') & (O.n_partial > 0) & (O.lots >= 2) & (O.dayno == 0)].sort_values(['und', 'expiry', 'tt_first']); r = bo.iloc[0]; add('body_partial', 'body order filled in several partial fills (>= 2 lots)', r.und, r.expiry, r.cp, r.dayno, r.tt_first)
Sx = O[O.module == 's_']
def near_stop_(r): w = Sx[(Sx.und == r.und) & (Sx.expiry == r.expiry)]; return bool((np.abs(w.tt_dec.values - r.tt_first) <= 120).any())
bo2 = bo[[not near_stop_(r) for r in bo.itertuples()]]; r = bo2.iloc[0]; add('body_partial_no_stop', 'same rule, first instance not within 120 s of a stop-module order', r.und, r.expiry, r.cp, r.dayno, r.tt_first, 8, 25)
x = BL[(BL.matched) & (BL.lag > 10)].sort_values(['und', 'expiry', 'tt']); r = x.iloc[0]; add('delayed_hedge', 'wing decision more than 10 s after the body fill', r.und, r.expiry, r.cp, r.dayno, r.tt, 8, 40)
x = G[G.complete & (np.sign(G.sw) == np.sign(G.gap_before)) & (G.sw != G.gap_before) & (G.dayno == 1)].sort_values(['und', 'expiry', 'tt_dec']); r = x.iloc[0]; add('quantity_differs', 'wing signed lots differ from S-L at decision (sign right)', r.und, r.expiry, r.cp, r.dayno, r.tt_dec, 25, 15)
x = A[(A.cls == 'other_imbalanced')].sort_values(['und', 'expiry', 't0']); r = x.iloc[0]; add('missing_hedge', 'non-responding body burst, book stays imbalanced (unexplained class)', r.und, r.expiry, r.cp, r.day, r.t0, 15, 60)
RO = pd.read_csv(f'{OUT}/bh_b1_order_roles.csv', dtype={'tag': str}); RO = RO[RO.role == 'open_short']
def has_open_short(r): z = RO[(RO.und == r.und) & (RO.expiry == r.expiry) & (RO.cp == r.cp) & (RO.dayno == r.day) & (RO.te >= r.t0 - 1) & (RO.te <= r.t1 + 1)]; return len(z) > 0
x = A[(A.cls == 'balanced') & (A.dS > 0) & (A.day == 1)]; x = x[[has_open_short(r) for r in x.itertuples()]].sort_values(['und', 'expiry', 't0']); r = x.iloc[0]; add('existing_inventory', 'burst containing a new short sale answered by no hedge because L >= S already', r.und, r.expiry, r.cp, r.day, r.t0, 20, 30)
x = Q[(Q.cls == 'other_imbalanced') & (Q.gap_all < 0)].sort_values(['und', 'expiry', 'tt']); r = x.iloc[0]; add('body_exits_hedge_stays', 'quiet-time over-hedge: shorts gone, longs remain', r.und, r.expiry, r.cp, r.dayno, r.tt, 40, 40)
x = G[G.complete & (G.side == 'Sell') & (G.gap_before >= 0) & (G.dayno == 1)].sort_values(['und', 'expiry', 'tt_dec']); r = x.iloc[0]; add('hedge_exits_first', 'wing SELL while S >= L (no excess longs)', r.und, r.expiry, r.cp, r.dayno, r.tt_dec, 25, 15)
md = ['# Interaction timelines (cases chosen by pre-registered rules: first instance in cycle order)\n']; idx = []
for name, desc, u, e, cp, d, t0, lo, hi in cases:
    T = timeline(u, e, cp, d, t0 - lo, t0 + hi); md.append(f'## {name}\n**Rule:** {desc}.  **Cycle:** {u} expiry {e}, right {cp}, {["D-1", "D0"][d]}\n\n' + T.drop(columns=['tag']).to_markdown(index=False) + '\n' if False else f'## {name}\n**Rule:** {desc}.  **Cycle:** {u} expiry {e}, right {cp}, {["D-1", "D0"][d]}\n\n' + '| ' + ' | '.join(T.columns[:-1]) + ' |\n|' + '---|' * (len(T.columns) - 1) + '\n' + '\n'.join('| ' + ' | '.join(str(v) for v in row[:-1]) + ' |' for row in T.values) + '\n')
    idx.append((name, u, e, cp, d, hms(t0), len(T)))
open(f'{OUT}/bh_i1_cases.md', 'w').write('\n'.join(md)); pd.DataFrame(idx, columns=['case', 'und', 'expiry', 'cp', 'day', 'time', 'events']).to_csv(f'{OUT}/bh_i1_cases_index.csv', index=False)
print(pd.DataFrame(idx, columns=['case', 'und', 'expiry', 'cp', 'day', 'time', 'events']).to_string(index=False)); print(open(f'{OUT}/bh_i1_cases.md').read()[:2200])
