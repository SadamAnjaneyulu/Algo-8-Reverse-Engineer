"""TP-03 Phase 1 step 1: opportunity (window-level) dataset in three views, state features at the common primary snapshot and the S1 sensitivity, off-window body-short events.
Run: ALGO8_MARKET_DIR=... python3 tp_reconstruction/tp03/scripts/p1_dataset.py   (entry reconstruction only; no hypothesis test is run here)"""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tp03_common as tc, entry_common as ec
tc.assert_frozen()
OUT = tc.ANALYSIS
D = ec.Data(); BASE = ec.BASE; B0, B1 = ec.B0, ec.B1
I = D.I.copy(); I['date'] = I.ts.dt.normalize(); bars = {k: set(g.ts) for k, g in I.groupby(['und', 'date'])}
OP = D.OP; Pn = D.parents
first_body_E = Pn.groupby(['und', 'expiry']).E.min()                       # cycle's first body-short order-entry minute (entry reference for the since-entry features)
rows = []; offw = []
for c in D.cycles.itertuples():
    for kind, d, wins in (('PRE', c.first if c.has_pre else None, sorted(ec.PRE_REG + ec.PRE_CTRL)), ('D0', c.expiry if c.has_d0 else None, ec.D0_WIN)):
        if d is None: continue
        d = pd.Timestamp(d); sess = D.L[(D.L.und == c.und) & (D.L.expiry == c.expiry) & (D.L.date == d)]; ffs = sess.t_fill.min(); par = Pn[(Pn.und == c.und) & (Pn.expiry == c.expiry) & (Pn.date == d)]
        opn = OP[(OP.und == c.und) & (OP.expiry == c.expiry) & (OP.date == d)]; body = opn[(opn.sgn < 0) & (opn.module == 'num')]; stop_t = D.stops.get((c.und, c.expiry), pd.NaT)
        E0 = first_body_E.get((c.und, c.expiry), pd.NaT); entry_straddle = D.atm_straddle(c.und, c.expiry, E0 - pd.Timedelta(minutes=1)) if pd.notna(E0) else np.nan
        prev_snap = None; attributed_any = set()
        for T in wins:
            t, w0, w1, snap = ec.window_times(d, T); w1m = w1.floor('min')
            cl = par.apply(lambda r: ec.attribution_class(r.E, r.first_fill, (t, w0, w1, snap)), axis=1) if len(par) else pd.Series(dtype=object)
            p_in = par[cl == 'ENTERED_INSIDE_WINDOW']; p_amb = par[cl == 'AMBIGUOUS_BOUNDARY_MINUTE']; p_dec = par[cl == 'DECISION_IN_WINDOW_FILL_OUTSIDE']; p_bef = par[cl == 'SUBMITTED_BEFORE_WINDOW']
            attributed_any |= set(p_in.parent_oid) | set(p_amb.parent_oid) | set(p_dec.parent_oid)
            q = lambda p: (float(p.base_units.sum()), float(p[p.cp == 'CE'].base_units.sum()), float(p[p.cp == 'PE'].base_units.sum()))
            q_incl = q(pd.concat([p_in, p_amb, p_dec])); q_excl = q(pd.concat([p_in, p_dec]))
            fb = body[(body.t_fill >= w0) & (body.t_fill < w1)]; q1 = (float(fb.open_qty.sum() / BASE[c.und]), float(fb[fb.cp == 'CE'].open_qty.sum() / BASE[c.und]), float(fb[fb.cp == 'PE'].open_qty.sum() / BASE[c.und]))
            other = opn[(opn.t_fill >= w0) & (opn.t_fill < w1) & ~((opn.sgn < 0) & (opn.module == 'num'))]
            st = D.state(c.und, c.expiry, snap, entry_minute=E0 if pd.notna(E0) else None)
            a0 = st['short_units_CE'] + st['short_units_PE']
            stopped = pd.notna(stop_t) and stop_t < snap; before_start = snap < ffs.floor('min')
            act_nearby = len(sess[(sess.t_fill >= t - pd.Timedelta(minutes=30)) & (sess.t_fill <= t + pd.Timedelta(minutes=30)) & ~((sess.t_fill >= w0) & (sess.t_fill < w1))]) > 0
            have_bars = all(pd.Timestamp(x) in bars.get((c.und, d), set()) for x in pd.date_range(snap - pd.Timedelta(minutes=60), snap - pd.Timedelta(minutes=1), freq='min'))
            def quiet():
                if stopped or before_start or (kind == 'D0' and a0 <= 0): return 'NOT_APPLICABLE'
                return 'NO_ACTION_ACTIVE' if (act_nearby and have_bars) else 'NO_ACTION_UNCERTAIN'
            has_other = len(other) > 0
            v1 = 'ACTION' if len(fb) else ('ACTION_OTHER_CLASS' if has_other else quiet())
            n_incl = len(p_in) + len(p_amb) + len(p_dec); n_excl = len(p_in) + len(p_dec)
            v2 = 'ACTION' if n_incl else ('ACTION_OTHER_CLASS' if has_other else quiet())
            v3 = 'ACTION' if n_excl else ('AMBIGUOUS_ACTION' if len(p_amb) else ('ACTION_OTHER_CLASS' if has_other else quiet()))
            # S1 sensitivity: last completed minute before the first fill of the earliest attributed order (action); T for quiet windows
            att = pd.concat([p_in, p_amb, p_dec]); s1_t = (att.first_fill.min().floor('min') if len(att) else t.floor('min')); s1 = D.state(c.und, c.expiry, s1_t, entry_minute=E0 if pd.notna(E0) else None)
            f = dict(st); f1 = {k + '__S1': v for k, v in s1.items()}
            # derived features
            pw = np.nan
            if prev_snap is not None:
                a = D.idx_close(c.und, prev_snap - pd.Timedelta(minutes=1)); b = D.idx_close(c.und, snap - pd.Timedelta(minutes=1)); pw = 1e4 * np.log(b / a) if np.isfinite(a) and np.isfinite(b) and a > 0 else np.nan
            f['spot_ret_prev_window_bp'] = pw; sr = D.atm_straddle(c.und, c.expiry, snap - pd.Timedelta(minutes=1)); f['atm_straddle_premium_change_since_entry'] = (sr / entry_straddle - 1) * 100 if np.isfinite(sr) and np.isfinite(entry_straddle) and entry_straddle > 0 and snap > E0 else np.nan
            pw1 = np.nan
            if prev_snap is not None:
                a = D.idx_close(c.und, prev_snap - pd.Timedelta(minutes=1)); b = D.idx_close(c.und, s1_t - pd.Timedelta(minutes=1)); pw1 = 1e4 * np.log(b / a) if np.isfinite(a) and np.isfinite(b) and a > 0 else np.nan
            f1['spot_ret_prev_window_bp__S1'] = pw1; sr1 = D.atm_straddle(c.und, c.expiry, s1_t - pd.Timedelta(minutes=1)); f1['atm_straddle_premium_change_since_entry__S1'] = (sr1 / entry_straddle - 1) * 100 if np.isfinite(sr1) and np.isfinite(entry_straddle) and entry_straddle > 0 and s1_t > E0 else np.nan
            prev_snap = snap
            rows.append(dict(cycle=c.cycle, und=c.und, expiry=c.expiry, kind=kind, date=d, window=ec.lab(T), control_window=T in set(ec.PRE_CTRL), snapshot=snap, s1_snapshot=s1_t,
                             n_parents_before_window=len(p_bef), n_parents_inside=len(p_in), n_parents_ambiguous=len(p_amb), n_parents_decision_fill_outside=len(p_dec), n_body_short_fills_in_window=len(fb), n_other_class_openings=len(other),
                             view1_class=v1, view2_class=v2, view3_class=v3, Q_v1=q1[0], Q_CE_v1=q1[1], Q_PE_v1=q1[2], Q_v2=q_incl[0], Q_CE_v2=q_incl[1], Q_PE_v2=q_incl[2], Q_v3=q_excl[0], Q_CE_v3=q_excl[1], Q_PE_v3=q_excl[2],
                             activity_within_30m=act_nearby, bars_complete_60m=have_bars, stopped=stopped, before_session_start=before_start, short_units_at_snapshot=a0, **f, **f1))
        # ------------------------------------------------ off-window body-short parent orders (ENT-04), initial entry separated
        first_E = par.E.min() if len(par) else pd.NaT
        for r in par.itertuples():
            if r.parent_oid in attributed_any: continue
            wmin = min(abs((r.first_fill - (d + T)).total_seconds()) / 60 for T in wins); prev_close = D.RF[(D.RF.und == c.und) & (D.RF.expiry == c.expiry) & (D.RF.t_fill < r.first_fill) & (D.RF.close_qty > 0)].t_fill.max()
            offw.append(dict(cycle=c.cycle, und=c.und, kind=kind, date=d, parent_oid=r.parent_oid, cp=r.cp, strike=r.strike, order_entry_minute=r.E, first_fill=r.first_fill, units=r.units, base_units=r.base_units,
                             event_class=('INITIAL_ENTRY' if (kind == 'PRE' and r.E == first_E) else 'OFF_WINDOW_ACTION'), minutes_to_nearest_window=wmin, minutes_since_last_close=(r.first_fill - prev_close).total_seconds() / 60 if pd.notna(prev_close) else np.nan))
W = pd.DataFrame(rows); W.to_parquet(os.path.join(tc.DATA, 'p1_window_dataset.parquet'), index=False); O = pd.DataFrame(offw); O.to_csv(os.path.join(OUT, 'p1_off_window_events.csv'), index=False)
W.drop(columns=[c for c in W.columns if c.endswith('__S1')]).to_csv(os.path.join(OUT, 'p1_window_dataset.csv'), index=False)
pd.set_option('display.width', 250)
print(len(W), 'window rows;', len(O), 'off-window body-short parents'); print(W.groupby('kind')[['view1_class', 'view2_class', 'view3_class']].agg(lambda s: s.value_counts().to_dict()).to_string())
print(O.event_class.value_counts().to_string())
