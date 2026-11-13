"""TP-03 Phase 1 shared machinery (entry reconstruction): data loading, windows, submission attribution (three views), state features.
Every state feature is measured at ONE common snapshot, floor_minute(T - 2 s), with fills strictly before it and bars completed at or before the snapshot minus one minute;
an optional S1 snapshot (first fill of the attributed order) is the sensitivity. Nothing here uses information after the snapshot."""
import os, sys, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc
import market_data as md
CFG = tc.CFG; E_ = CFG['entry']; BASE = E_['base_units']; STEP = E_['strike_step']
B0 = pd.Timedelta(seconds=E_['window_bounds_seconds']['before']); B1 = pd.Timedelta(seconds=E_['window_bounds_seconds']['after'])
PKG_DATA = os.path.join(tc.PKG, 'data')
tmd = lambda s: pd.Timedelta(hours=int(s[:2]), minutes=int(s[3:]))
PRE_REG = [tmd(x) for x in E_['d1_windows']]; PRE_CTRL = [tmd(x) for x in E_['d1_control_windows']]
_d0 = E_['d0_windows']; D0_WIN = [tmd(_d0['start']) + pd.Timedelta(minutes=_d0['step_minutes'] * k) for k in range(int((tmd(_d0['end']) - tmd(_d0['start'])) / pd.Timedelta(minutes=_d0['step_minutes'])) + 1)]
lab = lambda T: f'{int(T.total_seconds() // 3600):02d}:{int(T.total_seconds() % 3600 // 60):02d}'


def window_times(date, T):
    """(T, W0 = T - 2 s, W1 = T + 3 min, snapshot = floor_minute(W0)) for a session date"""
    t = pd.Timestamp(date) + T; w0 = t - B0; return t, w0, t + B1, w0.floor('min')


def attribution_class(E, first_fill, T_ts):
    """submission class of a body parent order for the window of nominal time T_ts (E = order-entry minute stamp, minute precision); None if unrelated to the window"""
    t, w0, w1, w0m = T_ts; w1m = w1.floor('min'); fill_in = (first_fill >= w0) and (first_fill < w1)
    if fill_in:
        return 'SUBMITTED_BEFORE_WINDOW' if E < w0m else ('AMBIGUOUS_BOUNDARY_MINUTE' if E == w0m else 'ENTERED_INSIDE_WINDOW')
    if w0m < E < w1m: return 'DECISION_IN_WINDOW_FILL_OUTSIDE'
    return None


class Data:
    def __init__(self):
        self.L = pd.read_parquet(os.path.join(PKG_DATA, 'fill_event_ledger.parquet')); R = pd.read_parquet(os.path.join(PKG_DATA, 'fill_roles.parquet'))
        self.RF = R[R.method == 'FIFO'].merge(self.L[['src_row', 'und', 'expiry', 'date', 'cp', 'strike', 'module', 'parent_oid', 'order_entry_minute', 't_fill', 'qty_order', 'px_limit', 'order_status']], on='src_row')
        self.RA = R[R.method == 'AVG'][['src_row', 'inventory_after', 'ref_px_after']].rename(columns={'inventory_after': 'inv_avg', 'ref_px_after': 'ref_avg'})
        self.RF = self.RF.merge(self.RA, on='src_row').sort_values(['t_fill', 'src_row']).reset_index(drop=True)
        P = pd.read_parquet(os.path.join(PKG_DATA, 'reconstructed_position_ledger.parquet')); self.PC = P[(P.method == 'AVG') & (P.row_type == 'CLOSED')][['und', 'expiry', 'direction', 'pnl', 't_exit']].copy()
        self.I = md.index_bars(); self.O = md.option_bars()
        self.idx = {u: g.set_index('ts').sort_index() for u, g in self.I.groupby('und')}; self.opt = {c: (g.ts.values.astype('datetime64[ns]'), g.close.values) for c, g in self.O.groupby('contract_id')}
        self.cycles = self.L.groupby(['und', 'expiry']).agg(first=('date', 'min'), last=('date', 'max')).reset_index(); self.cycles['has_pre'] = self.cycles['first'] < self.cycles.expiry; self.cycles['has_d0'] = self.cycles['last'] == self.cycles.expiry
        self.cycles['cycle'] = self.cycles.und + '|' + self.cycles.expiry.dt.strftime('%Y-%m-%d')
        OP = self.RF[self.RF.open_qty > 0].copy(); self.OP = OP; self.stops = self.L[self.L.module == 's_'].groupby(['und', 'expiry']).t_fill.min()
        body = OP[(OP.sgn < 0) & (OP.module == 'num')]
        self.parents = body.groupby('parent_oid').agg(und=('und', 'first'), expiry=('expiry', 'first'), date=('date', 'first'), cp=('cp', 'first'), strike=('strike', 'first'), E=('order_entry_minute', 'first'), first_fill=('t_fill', 'min'), last_fill=('t_fill', 'max'),
                                                         units=('open_qty', 'sum'), fills=('src_row', 'size'), qty_order=('qty_order', 'first'), limit=('px_limit', 'first'), px_mean=('px_fill', 'mean')).reset_index()
        self.parents['base'] = self.parents.und.map(BASE); self.parents['base_units'] = self.parents.units / self.parents.base; self.parents['quote'] = self.parents.limit / 0.85       # the algorithm's own LTP for a sell (DAT-05)
        self.ev = {k: g.sort_values(['t_fill', 'src_row']) for k, g in self.RF.groupby(['und', 'expiry'])}

    # ---------------------------------------------------------------- state at a snapshot time (nothing at or after t)
    def state(self, und, expiry, t, entry_minute=None):
        """features at time t: fills strictly before t, bars with start <= floor(t) - 1 min"""
        f = {}; ev = self.ev[(und, expiry)]; ev = ev[ev.t_fill < t]; tm = t.floor('min'); last = tm - pd.Timedelta(minutes=1); step = STEP[und]
        # --- index features
        ix = self.idx[und]; ci = ix.close[ix.index <= last]; hi = ix.high[ix.index <= last]; lo = ix.low[ix.index <= last]
        sess = ix[(ix.index.normalize() == last.normalize()) & (ix.index <= last)]
        if len(ci) and ci.index[-1] == last:
            c0 = float(ci.iloc[-1]); get = lambda mins: (float(ix.close.get(last - pd.Timedelta(minutes=mins), np.nan)))
            f['spot_ret_15m_bp'] = 1e4 * math.log(c0 / get(15)) if np.isfinite(get(15)) else np.nan; f['spot_ret_60m_bp'] = 1e4 * math.log(c0 / get(60)) if np.isfinite(get(60)) else np.nan
            w = ix.loc[last - pd.Timedelta(minutes=30):last].close.values; f['rv30_bp'] = 1e4 * math.sqrt(float(np.sum(np.diff(np.log(w)) ** 2))) if len(w) >= 20 else np.nan
            h1 = ix.loc[last - pd.Timedelta(minutes=14):last]; h0 = ix.loc[last - pd.Timedelta(minutes=29):last - pd.Timedelta(minutes=15)]
            r0 = float(h0.high.max() - h0.low.min()) if len(h0) else np.nan; f['range_expansion'] = float((h1.high.max() - h1.low.min()) / r0) if len(h1) and r0 and r0 > 0 else np.nan
            f['dist_from_open_bp'] = 1e4 * math.log(c0 / float(sess.open.iloc[0])) if len(sess) else np.nan; spot = c0
            if entry_minute is not None and entry_minute < tm:
                ce = ix.close.get((entry_minute - pd.Timedelta(minutes=1)).floor('min'), np.nan); f['spot_ret_since_entry_bp'] = 1e4 * math.log(c0 / ce) if np.isfinite(ce) else np.nan
        else: spot = np.nan
        f['minutes_to_expiry'] = (pd.Timestamp(expiry) + pd.Timedelta(hours=15, minutes=30) - t).total_seconds() / 60
        # --- inventory
        last_fill = ev.groupby('contract_id').tail(1) if len(ev) else ev; inv = last_fill[last_fill.inventory_after != 0]
        for cp in ('CE', 'PE'):
            x = inv[inv.cp == cp]; f[f'short_units_{cp}'] = float((-x.inventory_after[x.inventory_after < 0]).sum()); f[f'long_units_{cp}'] = float(x.inventory_after[x.inventory_after > 0].sum()); f[f'net_units_{cp}'] = float(x.inventory_after.sum())
        # --- mark-to-market (average-cost basis) and the gross short notional proxy
        un_s = un_l = notional = 0.0
        for r in inv.itertuples():
            ts, cl = self.opt.get(r.contract_id, (None, None))
            if ts is None: continue
            j = np.searchsorted(ts, np.datetime64(last), 'right') - 1
            if j < 0: continue
            mk = float(cl[j]); u = np.sign(r.inv_avg) * (mk - r.ref_avg) * abs(r.inv_avg)
            if r.inv_avg < 0: un_s += u; notional += mk * abs(r.inv_avg)
            else: un_l += u
        pc = self.PC[(self.PC.und == und) & (self.PC.expiry == expiry) & (self.PC.t_exit < t)]
        rs = float(pc.pnl[pc.direction == -1].sum()); rl = float(pc.pnl[pc.direction == 1].sum())
        f['short_body_mtm'] = un_s + rs; f['wing_mtm'] = un_l + rl; f['cycle_mtm'] = un_s + rs + un_l + rl; f['gross_short_notional'] = notional
        # --- ATM premiums at the last completed bar (contracts Algo 8 traded only: NaN when no bar exists)
        pr = {}
        if np.isfinite(spot):
            K = int(round(spot / step) * step)
            for cp in ('CE', 'PE'):
                cid = f'{und}|{pd.Timestamp(expiry):%Y-%m-%d}|{cp}|{K}'; ts, cl = self.opt.get(cid, (None, None)); v = np.nan
                if ts is not None:
                    j = np.searchsorted(ts, np.datetime64(last), 'right') - 1; v = float(cl[j]) if j >= 0 and ts[j] == np.datetime64(last) else np.nan
                pr[cp] = v
        f['atm_ce_premium'] = pr.get('CE', np.nan); f['atm_pe_premium'] = pr.get('PE', np.nan)
        s = f['atm_ce_premium'] + f['atm_pe_premium']; f['ce_pe_premium_imbalance'] = (f['atm_ce_premium'] - f['atm_pe_premium']) / s if np.isfinite(s) and s > 0 else np.nan
        f['_atm_straddle'] = s
        # --- additions and closings so far in the cycle
        add = self.parents[(self.parents.und == und) & (self.parents.expiry == expiry) & (self.parents.first_fill < t)]; f['adds_so_far'] = int(len(add)); f['units_added_so_far'] = float(add.base_units.sum())
        cl_ = ev[(ev.close_qty > 0)]; f['minutes_since_last_close'] = (t - cl_.t_fill.max()).total_seconds() / 60 if len(cl_) else np.nan
        return f


FEATURES = ['spot_ret_since_entry_bp', 'spot_ret_prev_window_bp', 'spot_ret_15m_bp', 'spot_ret_60m_bp', 'rv30_bp', 'range_expansion', 'dist_from_open_bp', 'minutes_to_expiry', 'short_units_CE', 'short_units_PE', 'long_units_CE', 'long_units_PE', 'net_units_CE', 'net_units_PE',
            'cycle_mtm', 'short_body_mtm', 'wing_mtm', 'atm_ce_premium', 'atm_pe_premium', 'atm_straddle_premium_change_since_entry', 'ce_pe_premium_imbalance', 'adds_so_far', 'units_added_so_far', 'minutes_since_last_close', 'gross_short_notional']
