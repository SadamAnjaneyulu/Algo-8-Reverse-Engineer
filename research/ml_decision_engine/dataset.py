"""Canonical ledger adapter, fixed risk sets and causal portfolio features."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from .features import WINDOWS, market_features
from .checkpoints import CheckpointStore,publish_partial

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'research/outputs'
HERE = Path(__file__).resolve().parent
ROLES = ('short_open', 'short_close', 'long_open', 'long_close')
ACTION_NAMES = ('initial_entry', 'add_ce', 'add_pe', 'add_both', 'one_sided',
                'reduce_ce', 'reduce_pe', 'close_ce', 'close_pe', 'buy_protection',
                'sell_protection', 'replace_protection', 'reenter', 'flatten_short',
                'final_liquidation', 'reduce_contract', 'close_contract', 'hold')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def canonical_cache():
    """Reuse the established builder; redirect every regenerated output locally."""
    target = HERE/'.cache/canonical'
    if not (target/'cycle_34.npz').exists():
        path = ROOT/'research/hypothesis_controller_search/prepare.py'
        spec = importlib.util.spec_from_file_location('ml_canonical_prepare', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.CACHE = target
        module.OUT = HERE/'.cache/evidence'
        target.mkdir(parents=True, exist_ok=True)
        module.OUT.mkdir(parents=True, exist_ok=True)
        module.build()
    return target


class CanonicalState:
    """Consume audited before/after quantities and costs, never rematch old lots."""
    def __init__(self, C, rights, base):
        self.q = np.zeros(C, dtype=int)
        self.cost = np.full(C, np.nan)
        self.cash = np.zeros(2)
        self.realized = np.zeros(2)
        self.rights, self.base = rights, base
        self.epoch = np.full(C, np.nan)
        self.last_add = np.full(C, np.nan)
        self.last_close = np.full(C, np.nan)
        self.last_closed_pnl = np.full(C, np.nan)
        self.minimum = np.full(C, np.nan)
        self.side_peak = np.full(2, np.nan)
        self.basket_peak = np.nan
        self.previous_second = -1

    def consume(self, r, j):
        if int(self.q[j])!=int(r.quantity_before):
            raise AssertionError(('canonical quantity disagreement', r.source_row))
        old, new = self.q[j], int(r.quantity_after)
        rr = int(self.rights[j])
        self.cash[rr] += float(r.cash_change)
        self.realized[rr] += float(r.realized_pnl_change)
        self.q[j] = new
        self.cost[j] = float(r.average_cost_after) if new else np.nan
        if old==0 or old*new<0:
            self.epoch[j] = r.second
            self.minimum[j] = np.nan
        if r.opening_quantity>0:
            self.last_add[j] = r.second
        if r.closing_quantity>0:
            self.last_close[j] = r.second
            self.last_closed_pnl[j] = r.realized_pnl_change
        if new==0:
            self.epoch[j] = np.nan
            self.minimum[j] = np.nan
        self.previous_second = max(self.previous_second, int(r.second))

    def context(self, z, ti, second):
        q, p, rr = self.q, z['previous'][ti].astype(float), self.rights
        out = {}
        side_eq = []
        for right, name in [(0, 'ce'), (1, 'pe')]:
            live = (rr==right)&(q!=0)
            missing = int(np.sum(live&~np.isfinite(p)))
            eq = self.cash[right]+np.dot(q[live], p[live]) if not missing else np.nan
            side_eq.append(eq)
            shorts, longs = (rr==right)&(q<0), (rr==right)&(q>0)
            out.update({f'{name}_short_units': float(-q[shorts].sum()/self.base),
                        f'{name}_long_units': float(q[longs].sum()/self.base),
                        f'{name}_net_units': float(q[rr==right].sum()/self.base),
                        f'{name}_equity': float(eq), f'{name}_realized': self.realized[right],
                        f'{name}_unrealized': eq-self.realized[right],
                        f'{name}_missing_marks': missing,
                        f'{name}_drawdown': max(0., self.side_peak[right]-eq) if np.isfinite(self.side_peak[right]) and np.isfinite(eq) else np.nan})
            denominator = -q[shorts].sum()
            out[f'{name}_protection_ratio'] = q[longs].sum()/denominator if denominator else np.nan
        out['basket_equity'] = float(sum(side_eq)) if all(np.isfinite(side_eq)) else np.nan
        out['basket_realized'] = float(self.realized.sum())
        out['basket_unrealized'] = out['basket_equity']-out['basket_realized']
        out['basket_drawdown'] = max(0., self.basket_peak-out['basket_equity']) if np.isfinite(self.basket_peak) and np.isfinite(out['basket_equity']) else np.nan
        out['latest_fill_second'] = self.previous_second
        live = q!=0
        out['gross_premium'] = np.dot(np.abs(q[live]), p[live]) if np.isfinite(p[live]).all() else np.nan
        out['net_premium'] = np.dot(q[live], p[live]) if np.isfinite(p[live]).all() else np.nan
        for key in ['delta', 'gamma', 'vega']:
            values = z[key][ti].astype(float)
            out['book_'+key] = np.dot(q[live], values[live]) if np.isfinite(values[live]).all() else np.nan
        spot, sigma, days = z['feature'][ti, [0, 6, 7]]
        # Flat ATM surface, spot/zero-rate European approximation, per calendar day.
        out['book_theta'] = -.5*out['book_gamma']*spot*spot*(sigma/100)**2/365 if days>0 else np.nan
        out['greeks_modelled'] = True
        for name, mask in [('short', q<0), ('protection', q>0)]:
            out[name+'_unrealized'] = np.dot(q[mask], p[mask]-self.cost[mask]) if np.isfinite(p[mask]).all() else np.nan
        return out

    def advance_peaks(self, context, prices):
        for r, name in enumerate(['ce', 'pe']):
            e = context[name+'_equity']
            if np.isfinite(e):
                self.side_peak[r] = max(self.side_peak[r], e) if np.isfinite(self.side_peak[r]) else e
        e = context['basket_equity']
        if np.isfinite(e):
            self.basket_peak = max(self.basket_peak, e) if np.isfinite(self.basket_peak) else e
        mask = (self.q<0)&np.isfinite(prices)
        self.minimum[mask] = np.fmin(self.minimum[mask], prices[mask])


def load_market():
    sys.path.insert(0, str(ROOT/'research'))
    from analyze_index_triggers import load_index
    index, _ = load_index()
    result = {}
    previous_close = {}
    for (u, day), bars in sorted(index.items()):
        b = pd.DataFrame(bars).set_index('t')
        b.index = pd.DatetimeIndex(b.index)
        f = market_features(b)
        f['rv_change_5'] = f.rv_15-f.rv_15.shift(5)
        prior = previous_close.get(u)
        f['opening_gap_pct'] = 100*(b.open.iloc[0]/prior-1) if prior else np.nan
        # This is preceding RECEIVED day, not certified preceding exchange session.
        f['prior_close_date'] = previous_close.get((u, 'date'), '')
        previous_close[u] = float(b.close.iloc[-1])
        previous_close[(u, 'date')] = day
        result[(u, day)] = f
    return result


def actions_for(before, after, flow, right=None, initial=False, reenter=False, final=False):
    ce, pe = flow[0], flow[1]
    result = {a: False for a in ACTION_NAMES}
    result.update(initial_entry=initial and ce[0]>0 and pe[0]>0,
                  add_ce=ce[0]>0, add_pe=pe[0]>0, add_both=ce[0]>0 and pe[0]>0,
                  one_sided=(ce[0]>0)!=(pe[0]>0),
                  reduce_ce=ce[1]>0, reduce_pe=pe[1]>0,
                  close_ce=ce[1]>0 and before[0]>0 and after[0]==0,
                  close_pe=pe[1]>0 and before[1]>0 and after[1]==0,
                  buy_protection=ce[2]+pe[2]>0, sell_protection=ce[3]+pe[3]>0,
                  replace_protection=ce[2]+pe[2]>0 and ce[3]+pe[3]>0,
                  reenter=reenter, flatten_short=sum(before)>0 and sum(after)==0,
                  final_liquidation=final and sum(before)>0 and sum(after)==0)
    if right is not None:
        other = 1-right
        for a in (['add_pe','reduce_pe','close_pe'] if other else ['add_ce','reduce_ce','close_ce']):
            result[a] = False
        result['add_both'] = result['one_sided'] = False
        result['initial_entry'] = False
        result['buy_protection'] = flow[right,2]>0
        result['sell_protection'] = flow[right,3]>0
        result['replace_protection'] = flow[right,2]>0 and flow[right,3]>0
        result['flatten_short'] = before[right]>0 and after[right]==0
        result['final_liquidation'] = final and result['flatten_short']
    result['hold'] = not any(result.values())
    return result


def build_dataset(out,resume_signature=None):
    cache = canonical_cache()
    meta_path = HERE/'.cache/evidence/cycle_metadata.json'
    metas = json.loads(meta_path.read_text())
    fills = pd.read_csv(SOURCE/'playbook_fill_ledger.csv.gz')
    fills['second'] = pd.to_datetime(fills.timestamp_ist).astype('int64')//10**9
    market = load_market()
    chunks, audit = [], []
    store=CheckpointStore(out,resume_signature) if resume_signature else None
    for meta in metas:
        cid, u, expiry = meta['cycle_id'], meta['underlying'], meta['expiry_date']
        cached=store.load(f'dataset_cycle_{cid:02}') if store else None
        if cached is not None:
            chunks.append(out/cached['path']);audit.extend(cached['audit'])
            print('Resumed dataset cycle',cid,flush=True);continue
        audit_start=len(audit)
        with np.load(cache/f'cycle_{cid:02}.npz') as a:
            z = {k:a[k] for k in a.files}
        T, C = z['observed'].shape
        base, step = int(z['base']), int(z['step'])
        lookup = {(int(k), 'PE' if r else 'CE'):j for j,(k,r) in enumerate(zip(z['strikes'], z['rights']))}
        fs = fills[fills.underlying.eq(u)&fills.expiry_date.eq(expiry)].sort_values(['second','source_row'])
        records = list(fs.itertuples()); pointer = 0
        batches = {int(t):g for t,g in fs.groupby(fs.second//60)}
        state = CanonicalState(C, z['rights'], base)
        first_short = int(fs[(fs.side=='Sell')&fs.opening_quantity.gt(0)].second.min())
        last_open = {rr: int(fs[(fs.option_type==name)&(fs.side=='Sell')&fs.opening_quantity.gt(0)].second.max())
                     if len(fs[(fs.option_type==name)&(fs.side=='Sell')&fs.opening_quantity.gt(0)]) else -1
                     for rr,name in enumerate(['CE','PE'])}
        rows = []
        for ti in range(T):
            t = int(z['minutes'][ti])*60
            while pointer<len(records) and records[pointer].second<t:
                r = records[pointer]; state.consume(r, lookup[(r.strike,r.option_type)]); pointer += 1
            if ti and z['minutes'][ti]-z['minutes'][ti-1]==1:
                assert np.array_equal(state.q, z['observed'][ti-1])
            stamp = pd.Timestamp(t, unit='s', tz='UTC').tz_convert('Asia/Kolkata')
            day = str(stamp.date()); clock = int(z['clock'][ti])
            # Opportunities extend through the canonical received session calendar.
            ctx = state.context(z, ti, t)
            frame = market.get((u,day))
            m = frame.loc[stamp].to_dict() if frame is not None and stamp in frame.index else {}
            m.pop('prior_close_date', None)
            m.update(atm_iv_pct=float(z['feature'][ti,6]), tau_days=float(z['feature'][ti,7]))
            for unavailable in ['atm_ce_own_iv','atm_pe_own_iv','iv_skew','iv_term_structure',
                                'bid_ask_spread','certified_liquidity','broker_delta','broker_gamma','broker_theta','broker_vega']:
                m[unavailable]=np.nan
            spot=m.get('spot',np.nan)
            atm=int(np.floor(spot/step+.5)*step) if np.isfinite(spot) else None
            premiums=[]
            for right,name in [(0,'ce'),(1,'pe')]:
                matches=np.flatnonzero((z['strikes']==atm)&(z['rights']==right)) if atm is not None else []
                p=float(z['previous'][ti,matches[0]]) if len(matches) else np.nan
                m[f'atm_{name}_premium']=p;premiums.append(p)
            m['atm_combined_premium']=sum(premiums) if all(np.isfinite(premiums)) else np.nan
            for w in WINDOWS:
                valid = ti>=w and z['minutes'][ti]-z['minutes'][ti-w]==w and z['session'][ti]==z['session'][ti-w]
                m[f'iv_change_{w}'] = float(z['feature'][ti,6]-z['feature'][ti-w,6]) if valid else np.nan
            m['iv_minus_rv15'] = m['atm_iv_pct']-m.get('rv_15', np.nan)*np.sqrt(252*375/15)
            flow_contract = np.zeros((C,4), dtype=float)
            batch = batches.get(t//60)
            source_rows = ''
            if batch is not None:
                source_rows = ';'.join(batch.source_row.astype(str))
                for r in batch.itertuples():
                    j = lookup[(r.strike,r.option_type)]
                    flow_contract[j,0 if r.side=='Sell' else 2] += r.opening_quantity
                    flow_contract[j,1 if r.side=='Buy' else 3] += r.closing_quantity
            flow = np.array([flow_contract[z['rights']==r].sum(axis=0) for r in (0,1)])
            before = np.array([-state.q[(z['rights']==r)&(state.q<0)].sum() for r in (0,1)])
            # Labels include complete next-minute atomic transitions, not features.
            after_q = z['observed'][ti]
            after = np.array([-after_q[(z['rights']==r)&(after_q<0)].sum() for r in (0,1)])
            common = dict(cycle_id=cid, underlying=u, expiry_date=expiry,
                first_session=meta['dates'][0], timestamp_ist=stamp.isoformat(), second=t,
                phase='expiry' if day==expiry else 'preexpiry', known_initialization=meta['dates'][0]<expiry,
                level='basket', strike=0, option_type='BOTH', clock_minute=clock,
                clock_sin=np.sin(2*np.pi*clock/1440), clock_cos=np.cos(2*np.pi*clock/1440),
                minute_mod15=clock%15, initial_window=clock in range(555,559),
                scheduled_window=clock in [570,585,600,615,630,645,660,675,690,705,720,750,810,825,840,855,870],
                minutes_to_next_quarter=15-clock%15, previously_inspected=True,
                decision_time_observed=False, y_source_rows=source_rows,
                last_label_second=t+60, **ctx, **m)
            initial = t<=first_short<t+60 and day<expiry
            final = day==expiry and clock>=900 and t>max(last_open.values()) and not np.any(z['observed'][-1]<0)
            re = bool(np.any((flow_contract[:,0]>0)&np.isfinite(state.last_close)&(state.q>=0)))
            def append(level, right, j=None):
                x = dict(common, level=level)
                fl = flow if j is None else np.array([flow_contract[j] if r==right else np.zeros(4) for r in (0,1)])
                b, a = before, after
                if j is not None:
                    b = np.array([max(-state.q[j],0) if r==right else 0 for r in (0,1)])
                    a = np.array([max(-after_q[j],0) if r==right else 0 for r in (0,1)])
                labels = actions_for(b,a,fl,right,initial,re,final)
                if right is not None:
                    x['option_type'] = 'PE' if right else 'CE'
                    x['side_units'] = common[('pe' if right else 'ce')+'_short_units']
                if j is not None:
                    p, cost = float(z['previous'][ti,j]), state.cost[j]
                    x.update(strike=int(z['strikes'][j]), contract_units=float(state.q[j]/base),
                        option_mark=p, entry_cost=cost,
                        premium_loss_pct=100*(p/cost-1) if state.q[j]<0 and p>0 and cost>0 else np.nan,
                        premium_capture_pct=100*(1-p/cost) if state.q[j]<0 and p>0 and cost>0 else np.nan,
                        trailing_rebound_pct=100*(p/np.fmin(state.minimum[j],p)-1) if state.q[j]<0 and p>0 and np.isfinite(state.minimum[j]) else np.nan,
                        position_age_minutes=(t-state.epoch[j])/60,
                        since_contract_add_minutes=(t-state.last_add[j])/60,
                        since_contract_close_minutes=(t-state.last_close[j])/60,
                        previous_closed_pnl=state.last_closed_pnl[j],
                        relative_strike_grids=(z['strikes'][j]-m.get('spot',np.nan))/step,
                        previous_bar_volume=float(z['previous_volume'][ti,j]),
                        contract_delta=float(z['delta'][ti,j]), contract_gamma=float(z['gamma'][ti,j]),
                        contract_vega=float(z['vega'][ti,j]))
                    for w in WINDOWS:
                        valid=ti>=w and z['minutes'][ti]-z['minutes'][ti-w]==w and z['session'][ti]==z['session'][ti-w]
                        old=z['previous'][ti-w,j] if valid else np.nan
                        x[f'premium_change_{w}']=100*(p/old-1) if p>0 and old>0 else np.nan
                    labels['reduce_contract'] = fl[:,1].sum()>0
                    labels['close_contract'] = labels['reduce_contract'] and a.sum()==0 and b.sum()>0
                    labels['reenter'] = flow_contract[j,0]>0 and np.isfinite(state.last_close[j]) and state.q[j]>=0
                for action,value in labels.items():
                    x['y_'+action] = int(value)
                x['y_new_short'] = int(fl[:,0].sum()>0)
                for rr,name in enumerate(['ce','pe']):
                    for k,role in enumerate(ROLES):
                        x['y_'+name+'_'+role+'_units'] = fl[rr,k]/base
                x['y_any_action'] = int(fl.sum()>0)
                x['y_hold'] = int(not x['y_any_action'])
                rows.append(x)
            append('basket', None)
            for rr in (0,1):
                append('side', rr)
            candidates = np.flatnonzero(np.isfinite(z['previous'][ti])|(state.q!=0))
            for j in candidates:
                append('contract', int(z['rights'][j]), int(j))
            uncovered = np.setdiff1d(np.flatnonzero(flow_contract.sum(axis=1)>0), candidates)
            audit.append(dict(cycle_id=cid, second=t, total_action_contracts=int((flow_contract.sum(axis=1)>0).sum()),
                              uncovered_action_contracts=len(uncovered), candidate_contracts=len(candidates),
                              latest_fill_second=state.previous_second,
                              strictly_prior_fills=state.previous_second<t,
                              market_boundary_valid=m.get('market_available_second',t)<=t))
            state.advance_peaks(ctx,z['previous'][ti])
        part = pd.DataFrame(rows)
        part.insert(0,'observation_id',[f'C{cid:02}-{i:08}' for i in range(len(part))])
        # Compact each cycle before concatenation, not after making multiple
        # full-size copies of the complete risk set on a bounded cloud runner.
        categories={'underlying':['NIFTY','SENSEX'],'phase':['preexpiry','expiry'],
                    'level':['basket','side','contract'],'option_type':['BOTH','CE','PE']}
        for col,values in categories.items():
            part[col]=pd.Categorical(part[col],categories=values)
        for col in part:
            if col.startswith('y_') and not col.endswith('_units') and col!='y_source_rows':
                part[col]=part[col].astype('int8')
            elif part[col].dtype=='float64' and not any(k in col for k in ['second','cost','equity','realized']):
                part[col]=part[col].astype('float32')
        for col in ['timestamp_ist','expiry_date','first_session','y_source_rows']:
            part[col]=part[col].astype('category')
        path=out/f'.dataset_cycle_{cid:02}.parquet'
        part.to_parquet(path,index=False); chunks.append(path)
        if store:store.save(f'dataset_cycle_{cid:02}',dict(path=path.name,audit=audit[audit_start:]),[path])
        publish_partial(out,'dataset',len(chunks),len(metas))
        print('Dataset cycle',cid,'rows',len(part),flush=True)
    import pyarrow.parquet as pq
    # Schema union through pandas handles early cycles with no live contract features.
    frames=[pd.read_parquet(p) for p in chunks]
    dataset=pd.concat(frames,ignore_index=True)
    for col in ['timestamp_ist','expiry_date','first_session','y_source_rows']:
        dataset[col]=dataset[col].astype('category')
    for col in dataset.select_dtypes('float64'):
        if 'second' not in col and 'cost' not in col and 'equity' not in col and 'realized' not in col:
            dataset[col]=dataset[col].astype('float32')
    dataset.to_parquet(out/'canonical_ml_decision_dataset.parquet',index=False)
    pd.DataFrame(audit).to_csv(out/'risk_set_coverage.csv',index=False)
    quality=[]
    for level,g in dataset.groupby('level'):
        for col in g:
            quality.append(dict(level=level,feature=col,rows=len(g),available=int(g[col].notna().sum()),
                coverage=float(g[col].notna().mean()),unique_values=int(g[col].nunique()),
                provenance='outcome' if col.startswith('y_') else 'modelled' if any(k in col for k in ['gamma','delta','vega','theta','iv']) else 'canonical_or_lagged',
                independent_cycles=int(g.cycle_id.nunique())))
    pd.DataFrame(quality).to_csv(out/'feature_coverage_and_quality.csv',index=False)
    assert all(x['strictly_prior_fills'] and x['market_boundary_valid'] for x in audit)
    assert len(fills)==41421
    return dataset,metas
