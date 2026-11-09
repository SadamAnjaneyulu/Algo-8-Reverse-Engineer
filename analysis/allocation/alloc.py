"""Allocation definitions and the per-allocation ledger.  Allocation ids are NOT in the broker export, so an 'allocation' is a hypothesis.
Three definitions are built from the same clean order table (col 163 key) and reported separately; none is assumed correct:
  (a) SLOT   : one allocation per (cycle, date, schedule slot k, right).  Slot k = nearest 09:16 + 15k clock; an entry belongs to it if its first
               fill is in [clock - 2 s, clock + 3 min)  (the window lineage X used; lineage Y floors to the minute -> [clock, clock + 3 min)).
               Entries outside every window are 'extra': one allocation per (cycle, date, sale burst, right).
  (b) CHAIN  : lineage Y's timer-phase chains (analysis/chains.py algorithm, copied unchanged), re-run on bursts rebuilt from the CLEAN order table
               (burst = body sells more than 4 s apart; this gap reproduces the legacy cache's 5,481 bursts exactly on the legacy, reused-key table).
               One allocation per (underlying, date, chain); bursts not in a significant chain are their own allocation.
               Deviation from the legacy script: detection is per (underlying, date) because the legacy cache had no underlying column.
  (c) LOT    : every unit lot is its own allocation (entry order id); which lot a buy-back closes is a convention (cheap / fifo / lifo).
Wings (long entries) are attached to the body-sell allocation of the same right whose first fill is nearest within +-10 s, else 'unlinked'.
Which allocation a buy-back closes is not observable: every closing assignment below is by the stated lot convention and is labelled as such.
python3 analysis/allocation/alloc.py -> results/allocation_ledger_{slot,chain}.csv, allocation_lots.csv.gz, allocation_summary.txt"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE)
sys.path.insert(0, AN); sys.path.insert(0, os.path.join(AN, 'exit_engine'))
import numpy as np, pandas as pd
from scipy.stats import poisson
from common import orders, replay_book, markets, C
RES = os.path.join(HERE, 'results'); os.makedirs(RES, exist_ok=True)
GAP_S, PRE_S, POST_S, WING_S = 4, 2, 180, 10
W, STEP, PTHR = 30, 5, 1e-4          # chains.py constants, unchanged

def slot_of(t):
    """(k, offset_seconds) of the nearest 09:16 + 15k clock, or (-1, nan) if t is not within [clock - 2 s, clock + 180 s) of any clock."""
    s = (t - t.normalize()).total_seconds() - (9 * 3600 + 16 * 60)
    k = int(np.floor((s + PRE_S) / 900)); off = s - 900 * k
    return (k, off) if (k >= 0 and k <= 24 and -PRE_S <= off < POST_S) else (-1, np.nan)

def bursts_from_sells(sells):
    """sells: body Sell orders with t_fill.  Returns sells with 'burst' = id per (und, date) of runs separated by > GAP_S seconds."""
    s = sells.sort_values(['und', 'date', 't_fill', 'oid']).copy()
    gap = s.groupby(['und', 'date']).t_fill.diff().dt.total_seconds()
    s['burst'] = ((gap.isna()) | (gap > GAP_S)).groupby([s.und, s.date]).cumsum().astype(int)
    return s

def detect_chains(b):
    """chains.py algorithm on a burst frame with columns date, sec (seconds since 09:15:00 of the burst's first fill); returns chain id per burst (-1 none)."""
    b = b.copy(); b['ph'] = b.sec % 900; b['q'] = (b.sec // 900).astype(int); b['chain'] = -1; cid = 0
    for _, g in b.groupby('date'):
        nq = g.q.nunique(); lam = nq * W / 900; cands = []
        for c in np.arange(0, 900, STEP):
            dphi = (g.ph - c + 450) % 900 - 450
            k = g[(dphi >= -W / 2) & (dphi < W / 2)].q.nunique()
            if k >= 3: cands.append((poisson.sf(k - 1, lam), -k, c))
        cands.sort(); chosen = []
        for p, negk, c in cands:
            if p >= PTHR: break
            if all(min(abs(c - c2), 900 - abs(c - c2)) > W for c2 in chosen): chosen.append(c)
        for c in chosen:
            dphi = (g.ph - c + 450) % 900 - 450
            b.loc[g.index[(dphi >= -W / 2) & (dphi < W / 2)], 'chain'] = cid; cid += 1
    return b

def build_allocations(o=None):
    """DataFrame indexed like the order table's entry orders: oid, alloc_slot, alloc_chain, alloc_lot, role (short / wing / lump / other)."""
    o = orders() if o is None else o
    e = o[o.label == 'open'].copy(); e['t'] = pd.to_datetime(e.t_fill)
    e['role'] = np.select([(e.side == 'Sell') & (e.tp == 'num'), (e.side == 'Buy') & (e.tp == 'v_'), (e.side == 'Buy')], ['short', 'lump', 'wing'], 'other')
    cyc = e.und + '|' + pd.to_datetime(e.expiry).dt.strftime('%Y-%m-%d'); dd = pd.to_datetime(e.date).dt.strftime('%Y-%m-%d')
    e['cyc'] = cyc; e['dstr'] = dd
    sh = bursts_from_sells(e[e.role == 'short'])
    firsts = sh.groupby(['und', 'date', 'burst']).t.min().rename('bt').reset_index()
    firsts['sec'] = (firsts.bt - firsts.bt.dt.normalize()).dt.total_seconds() - (9 * 3600 + 15 * 60)
    parts = []
    for u, g in firsts.groupby('und'): parts.append(detect_chains(g))
    ch = pd.concat(parts); sh = sh.merge(ch[['und', 'date', 'burst', 'chain']], on=['und', 'date', 'burst'], how='left')
    ks = [slot_of(t) for t in sh.t]; sh['k'] = [a for a, _ in ks]
    sh['alloc_slot'] = np.where(sh.k >= 0, sh.cyc + '|' + sh.dstr + '|S' + sh.k.astype(str) + '|' + sh.cp,
                                sh.cyc + '|' + sh.dstr + '|X' + sh.burst.astype(str) + '|' + sh.cp)
    sh['alloc_chain'] = np.where(sh.chain >= 0, sh.und + '|' + sh.dstr + '|C' + sh.chain.astype('Int64').astype(str) + '|' + sh.cp,
                                 sh.und + '|' + sh.dstr + '|U' + sh.burst.astype(str) + '|' + sh.cp)
    sh['alloc_lot'] = sh.oid
    # wings and lump: attach to the nearest short entry of the same (cycle, date, right) within WING_S seconds
    rest = e[e.role != 'short'].copy(); rest['alloc_slot'] = 'unlinked'; rest['alloc_chain'] = 'unlinked'; rest['alloc_lot'] = rest.oid
    key = ['und', 'expiry', 'date', 'cp']; shg = {k: g for k, g in sh.groupby(key)}
    for k, g in rest[rest.role == 'wing'].groupby(key):
        S = shg.get(k)
        if S is None: continue
        st = S.t.values.astype('datetime64[ns]').astype('int64'); wt = g.t.values.astype('datetime64[ns]').astype('int64')
        j = np.abs(st[None, :] - wt[:, None]).argmin(1); ok = np.abs(st[j] - wt) <= WING_S * 1e9
        idx = g.index[ok]; rest.loc[idx, 'alloc_slot'] = S.alloc_slot.values[j[ok]]; rest.loc[idx, 'alloc_chain'] = S.alloc_chain.values[j[ok]]
    out = pd.concat([sh, rest]).sort_values(['t', 'oid'])
    return out[['oid', 'und', 'expiry', 'date', 'cp', 'strike', 'role', 'lots', 't', 'vwap', 'alloc_slot', 'alloc_chain', 'alloc_lot', 'split']]

def lot_ledger(conv='cheap', A=None):
    """Unit-lot book (replay_book, convention `conv`) joined to the allocation ids of the lot's ENTRY order.  Closing ownership is by convention."""
    A = build_allocations() if A is None else A
    L = replay_book(conv); L = L.merge(A[['oid', 'role', 'alloc_slot', 'alloc_chain']], left_on='entry_oid', right_on='oid', how='left').drop(columns='oid')
    # 0.4 % of unit lots are opened by orders labelled as closes (an over-sized buy-back / salvage flips the position): they have no entry allocation
    for c in ('alloc_slot', 'alloc_chain'): L[c] = L[c].fillna('nonentry')
    L['role'] = L.role.fillna('nonentry')
    return L

def allocation_ledger(L, col):
    """One row per allocation: entries, hedge, closes by label, replacement / re-entry, final state.  Short lots only drive 'closed_*'."""
    s = L[(L.sgn < 0) & (L.role == 'short')]; w = L[(L.sgn > 0) & (L.role == 'wing')]
    g = s.groupby(col)
    led = g.agg(und=('und', 'first'), expiry=('expiry', 'first'), n_short_lots=('entry_oid', 'size'), n_entry_orders=('entry_oid', 'nunique'), n_strikes=('strike', 'nunique'),
                first_entry=('entry_t', 'min'), last_entry=('entry_t', 'max'), mean_entry_px=('entry_px', 'mean'), carried_lots=('carried', 'sum'), reentry_lots=('reentry', 'sum'),
                split=('split', 'first'))
    cl = s.assign(lab=s.exit_label.str.replace(r'^\d+b? ', '', regex=True)).pivot_table(index=col, columns='lab', values='entry_oid', aggfunc='size', fill_value=0)
    cl.columns = ['closed_' + c.replace(' ', '_')[:28] for c in cl.columns]
    led = led.join(cl)
    led['n_closed_lots'] = (s.exit_label != 'expired/open').groupby(s[col]).sum(); led['n_survive_lots'] = led.n_short_lots - led.n_closed_lots
    led['last_exit'] = s.groupby(col).exit_t.max()
    led['wing_lots'] = w.groupby(col).size().reindex(led.index).fillna(0).astype(int)
    led['wing_lots_released'] = w[w.exit_label.str.startswith('L-hedge release', na=False)].groupby(col).size().reindex(led.index).fillna(0).astype(int)
    return led.reset_index().rename(columns={col: 'allocation'})

def describe(A, L):
    lines = []
    for col in ('alloc_slot', 'alloc_chain'):
        sh = A[A.role == 'short']; n = sh.groupby(col).lots.sum()
        lines.append(f'{col}: {n.size} short allocations; lots per allocation mean {n.mean():.2f} median {n.median():.0f} p90 {n.quantile(.9):.0f} max {n.max():.0f}; '
                     f'{(n == 1).mean():.0%} are single-lot')
        lines.append(f'  wings linked: {(A[A.role == "wing"][col] != "unlinked").mean():.1%} of {int((A.role == "wing").sum())} wing entry orders')
    sh = A[A.role == 'short']; lines.append(f'on-grid slot share of short entry orders: {sh.alloc_slot.str.contains(r"\|S\d+\|").mean():.1%}')
    lines.append(f'chained share of short entry orders: {sh.alloc_chain.str.contains(r"\|C\d+\|").mean():.1%}')
    return '\n'.join(lines)

if __name__ == '__main__':
    A = build_allocations(); L = lot_ledger('cheap', A); txt = describe(A, L); print(txt)
    open(os.path.join(RES, 'allocation_summary.txt'), 'w').write(txt + '\n')
    for col, nm in (('alloc_slot', 'slot'), ('alloc_chain', 'chain')):
        allocation_ledger(L, col).to_csv(os.path.join(RES, f'allocation_ledger_{nm}.csv'), index=False)
    L[['und', 'expiry', 'cp', 'strike', 'sgn', 'role', 'entry_oid', 'entry_t', 'entry_px', 'exit_oid', 'exit_t', 'exit_px', 'exit_label', 'alloc_slot', 'alloc_chain', 'carried', 'reentry', 'split']].to_csv(
        os.path.join(RES, 'allocation_lots.csv.gz'), index=False, compression='gzip')
    print('saved')
