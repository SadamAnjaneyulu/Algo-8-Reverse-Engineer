"""Causal contract-side state, FIFO/LIFO allocation sensitivity and modeled Greeks."""
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import numpy as np
from scipy.special import ndtr

from audit_strike_hedge_rules import ROOT, OUT, Market, logs, reconstruct_parents
from refine_exit_scopes import RoleBook
from rank_trigger_probabilities import save_records

CAPITAL = 20_000_000


def vector_greeks(price, forward, strike, tau, call):
    price, forward, strike, tau = [np.asarray(a, float) for a in (price, forward, strike, tau)]
    call = np.asarray(call, bool)
    valid = np.isfinite(price + forward + strike + tau) & (forward > 0) & (strike > 0) & (tau > 0)
    f, k, t = np.maximum(forward, 1), np.maximum(strike, 1), np.maximum(tau, 1e-12)
    intrinsic = np.where(call, np.maximum(f-k, 0), np.maximum(k-f, 0))
    valid &= (price-intrinsic > .025) & (price < np.where(call, f, k))
    low, high = np.full(len(f), .0001), np.full(len(f), 5.)
    for iteration in range(36):
        sigma = (low+high)/2
        vol = sigma*np.sqrt(t)
        d1 = np.log(f/k)/vol+vol/2
        d2 = d1-vol
        value = np.where(call, f*ndtr(d1)-k*ndtr(d2), k*ndtr(-d2)-f*ndtr(-d1))
        low = np.where(value < price, sigma, low)
        high = np.where(value < price, high, sigma)
        if iteration == 0:
            vol5 = 5*np.sqrt(t)
            d15 = np.log(f/k)/vol5+vol5/2
            p5 = np.where(call, f*ndtr(d15)-k*ndtr(d15-vol5), k*ndtr(-d15+vol5)-f*ndtr(-d15))
            valid &= p5 >= price
    sigma = (low+high)/2
    vol = sigma*np.sqrt(t)
    d1 = np.log(f/k)/vol+vol/2
    density = np.exp(-d1*d1/2)/math.sqrt(2*math.pi)
    out = dict(iv_pct=100*sigma, delta=np.where(call, ndtr(d1), ndtr(d1)-1),
               gamma=density/(f*vol), vega_one_point=f*density*np.sqrt(t)*.01,
               theta_calendar_day=-f*density*sigma/(2*np.sqrt(t))/365)
    return {key: np.where(valid, value, np.nan) for key, value in out.items()}


class ShortLots:
    def __init__(self, lifo=False):
        self.lifo = lifo
        self.lots = defaultdict(list)
        self.closes = []

    def apply(self, fill, parent_id, entry_spot):
        key = (fill['strike'], fill['ot'])
        if fill['side'] == 'Sell' and fill['opening']:
            self.lots[key].append(dict(parent_id=parent_id, entry_ist=fill['t'].isoformat(),
                                       entry_date=str(fill['t'].date()), price=float(fill['price']),
                                       remaining=fill['opening'], entry_spot=entry_spot))
        if fill['side'] != 'Buy':
            return
        remaining = fill['q']-fill['opening']
        while remaining:
            index = -1 if self.lifo else 0
            lot = self.lots[key][index]
            quantity = min(remaining, lot['remaining'])
            self.closes.append(dict(parent_id=lot['parent_id'], entry_ist=lot['entry_ist'],
                                    exit_ist=fill['t'].isoformat(), quantity=quantity,
                                    entry_price=lot['price'], exit_price=float(fill['price']),
                                    short_realized_pnl=quantity*(lot['price']-float(fill['price']))))
            lot['remaining'] -= quantity
            remaining -= quantity
            if not lot['remaining']:
                self.lots[key].pop(index)


def lot_state(lots, price, day, spot):
    total = sum(lot['remaining'] for lot in lots)
    cost = sum(lot['remaining']*lot['price'] for lot in lots)/total if total else None
    changes = [(100*(price/lot['price']-1), lot['remaining']) for lot in lots] if price is not None else []
    anchor = sum(lot['entry_spot']*lot['remaining'] for lot in lots)/total if total and all(lot['entry_spot'] for lot in lots) else None
    return dict(cost=cost, max_loss_pct=max((a for a, q in changes), default=None),
                min_loss_pct=min((a for a, q in changes), default=None),
                fraction_over25=sum(q for a, q in changes if a >= 25)/total if changes else None,
                fraction_over50=sum(q for a, q in changes if a >= 50)/total if changes else None,
                fraction_over75=sum(q for a, q in changes if a >= 75)/total if changes else None,
                carried_fraction=sum(lot['remaining'] for lot in lots if lot['entry_date'] < day)/total if total else None,
                spot_since_entry_pct=100*(spot/anchor-1) if spot and anchor else None)


def main():
    fills = logs.read_fills()
    parents = reconstruct_parents(fills)
    parent_ids, parent_rows = {}, []
    for i, p in enumerate(sorted(parents, key=lambda x: (x['first'], x['sources']))):
        identifier = f'p{i+1}'
        for source in p['sources'].split(';'):
            parent_ids[int(source)] = identifier
        parent_rows.append(dict(parent_id=identifier, **{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in p.items()}))
    save_records('allocation_parent_inventory.csv', parent_rows)
    targets = defaultdict(int)
    for p in parents:
        if p['role'] == 'short_cover':
            targets[(p['underlying'], p['expiry_date'], p['strike'], p['option_type'], p['first'].replace(second=0))] += p['quantity']
    grouped, metadata = defaultdict(list), defaultdict(list)
    for r in fills:
        grouped[(r['u'], str(r['expiry']))].append(r)
    for path in (ROOT/'data/breeze/metadata/options').rglob('*.json'):
        m = json.loads(path.read_text())
        metadata[(m['contract']['underlying'], m['contract']['expiry_date'])].append(m)
    index, _ = logs.load_index()
    contract_rows, context_rows, closed_rows = [], [], []
    for (u, e), records in sorted(grouped.items()):
        market = Market(u, e, metadata[(u, e)], index)
        extra_quotes = {}
        for m in metadata[(u, e)]:
            c = m['contract']
            with (ROOT/'data/breeze'/m['normalized_path']).open() as stream:
                extra_quotes[(c['trade_date'], c['strike'], c['option_type'])] = {
                    r['timestamp_ist'][11:16]: dict(oi=float(r['open_interest']) if r['open_interest'] and float(r['open_interest']) > 0 else None,
                                                   close=float(r['close']), volume=float(r['volume'])) for r in csv.DictReader(stream)}
        book, fifo, lifo = RoleBook(), ShortLots(), ShortLots(True)
        last_cover, first_entry, trough = {}, {}, {}
        cursor, risks = 0, []
        local_context, local_contracts = [], []
        sessions = sorted({str(r['t'].date()) for r in records})
        for day in sessions:
            cash = {b['t'].strftime('%H:%M'): b for b in index.get((u, day), [])}
            previous_days = sorted(d for d in market.days if d < day)
            prior_day = previous_days[-1] if previous_days else None
            start = datetime.fromisoformat(day+'T09:15').replace(tzinfo=logs.IST)
            count = 385 if day >= '2026-08-03' else 375
            for offset in range(count+1):
                t = start+timedelta(minutes=offset)
                while cursor < len(records) and records[cursor]['t'] < t:
                    r = records[cursor]
                    key = (r['strike'], r['ot'])
                    guide, _ = logs.reference(index, u, r['t'])
                    parent_id = parent_ids[r['source']]
                    fifo.apply(r, parent_id, guide['close'] if guide else None)
                    lifo.apply(r, parent_id, guide['close'] if guide else None)
                    old = book.inventory[key]
                    book.apply(r)
                    if r['side'] == 'Buy' and r['q'] > r['opening']:
                        last_cover[key] = r['t']
                    if old >= 0 and book.inventory[key] < 0:
                        first_entry[key] = r['t']
                        trough[key] = float(r['price'])
                    if book.inventory[key] >= 0:
                        trough.pop(key, None)
                    cursor += 1
                previous = t-timedelta(minutes=1)
                clock = previous.strftime('%H:%M')
                state = market.state(day, clock)
                guide = cash.get(clock)
                past_cash = [b for b in cash.values() if b['t'] <= previous]
                last_cash = past_cash[-1] if past_cash else None
                spot = last_cash['close'] if last_cash else None
                cx = dict(underlying=u, expiry_date=e, date=day, clock=t.strftime('%H:%M'), cutoff_ist=t.isoformat(),
                          bar_start_ist=previous.isoformat(), phase='preexpiry' if day < e else 'expiry',
                          split='calibration' if e <= '2026-08-31' else 'evaluation',
                          g_spot=spot, g_tau_days=state['tau']*365 if state else None,
                          g_atm_iv_pct=state['iv']*100 if state else None,
                          g_spot_age_minutes=(previous-last_cash['t']).total_seconds()/60 if last_cash else None)
                for window in (5, 15, 30):
                    old = cash.get((previous-timedelta(minutes=window)).strftime('%H:%M'))
                    cx[f'g_spot_return{window}_pct'] = 100*(spot/old['close']-1) if spot and old else None
                    bars = [b for b in past_cash if b['t'] >= previous-timedelta(minutes=window-1)]
                    cx[f'g_range{window}_pct'] = 100*(max(b['high'] for b in bars)-min(b['low'] for b in bars))/bars[0]['open'] if len(bars) == window else None
                eq = {ot: book.cash[('short', ot)]+book.cash[('long', ot)] for ot in ('CE', 'PE')}
                missing = Counter()
                context_id = len(local_context)
                active = [(k, ot, q) for (k, ot), q in book.inventory.items() if q]
                for k, ot, q in active:
                    b = market.bar(day, k, ot, clock)
                    if b:
                        eq[ot] += q*b['close']
                    else:
                        missing[ot] += 1
                    risks.append((context_id, ot, q, b['close'] if b else np.nan,
                                  state['forward'] if state else np.nan, k, state['tau'] if state else np.nan, ot == 'CE', None))
                    if q > 0:
                        continue
                    price = b['close'] if b else None
                    if price is not None:
                        trough[(k, ot)] = min(trough.get((k, ot), price), price)
                    current = extra_quotes.get((day, k, ot), {}).get(clock)
                    other = extra_quotes.get((day, k, 'PE' if ot == 'CE' else 'CE'), {}).get(clock)
                    oldq = extra_quotes.get((day, k, ot), {}).get((previous-timedelta(minutes=5)).strftime('%H:%M'))
                    prior = market.bar(prior_day, k, ot, '15:39' if prior_day and prior_day >= '2026-08-03' else '15:29') if prior_day else None
                    opening = market.bar(day, k, ot, '09:15') if offset >= 1 else None
                    age = (t-last_cover[(k, ot)]).total_seconds()/60 if (k, ot) in last_cover else None
                    row = dict(underlying=u, expiry_date=e, date=day, clock=t.strftime('%H:%M'), cutoff_ist=t.isoformat(),
                               bar_start_ist=previous.isoformat(), cycle=u+'|'+e, strike=k, option_type=ot,
                               phase=cx['phase'], split=cx['split'], contract=u+'|'+e+'|'+str(k)+'|'+ot,
                               target_cover=int(targets[(u, e, k, ot, t)] > 0), target_cover_quantity=targets[(u, e, k, ot, t)],
                               g_short_units=-q/logs.UNIT[u], g_price=price,
                               g_cost=book.average[(k, ot)], g_loss_pct=100*(price/book.average[(k, ot)]-1) if price is not None else None,
                               g_trailing_recovery_pct=100*(price/trough[(k, ot)]-1) if price is not None and trough[(k, ot)] > 0 else None,
                               g_from_previous_close_pct=100*(price/prior['close']-1) if price is not None and prior and prior['close'] > 0 else None,
                               g_from_expiry_open_pct=100*(price/opening['open']-1) if price is not None and opening and opening['open'] > 0 and day == e else None,
                               g_age_minutes=(t-first_entry[(k, ot)]).total_seconds()/60,
                               g_since_cover_minutes=age, onset_eligible=int(age is None or age > 5),
                               g_oi=current['oi'] if current else None,
                               g_oi_change5_pct=100*(current['oi']/oldq['oi']-1) if current and oldq and current['oi'] and oldq['oi'] else None,
                               g_volume=current['volume'] if current else None,
                               g_same_strike_volume_ratio=current['volume']/other['volume'] if current and other and other['volume'] > 0 else None,
                               g_same_strike_oi_ratio=current['oi']/other['oi'] if current and other and current['oi'] and other['oi'] else None)
                    for mode, lots in [('fifo', fifo.lots[(k, ot)]), ('lifo', lifo.lots[(k, ot)])]:
                        if sum(a['remaining'] for a in lots) != -q:
                            raise ValueError('Lot attribution does not reconcile with inventory.')
                        row.update({f'g_{mode}_{name}': value for name, value in lot_state(lots, price, day, spot).items()})
                    row['g_adverse_spot_since_entry_pct'] = row['g_fifo_spot_since_entry_pct']*(1 if ot == 'CE' else -1) if row['g_fifo_spot_since_entry_pct'] is not None else None
                    for window in (5, 15, 30):
                        value = cx[f'g_spot_return{window}_pct']
                        row[f'g_adverse_spot{window}_pct'] = value*(1 if ot == 'CE' else -1) if value is not None else None
                    risks[-1] = risks[-1][:-1]+(len(local_contracts),)
                    local_contracts.append(row)
                for ot in ('CE', 'PE'):
                    cx[f'g_{ot}_equity_pct_capital'] = eq[ot]/CAPITAL*100 if not missing[ot] else None
                    cx[f'g_{ot}_short_units'] = sum(-q for k, right, q in active if right == ot and q < 0)/logs.UNIT[u]
                    cx[f'g_{ot}_long_units'] = sum(q for k, right, q in active if right == ot and q > 0)/logs.UNIT[u]
                local_context.append(cx)
        greeks = vector_greeks([r[3] for r in risks], [r[4] for r in risks], [r[5] for r in risks], [r[6] for r in risks], [r[7] for r in risks])
        aggregate = defaultdict(Counter)
        bad, total = Counter(), Counter()
        for i, (context_id, ot, q, p, f, k, tau, call, rowid) in enumerate(risks):
            total[context_id] += 1
            if not np.isfinite(greeks['delta'][i]):
                bad[context_id] += 1
            else:
                for field in ('delta', 'gamma', 'vega_one_point', 'theta_calendar_day'):
                    aggregate[(context_id, 'book')][field] += q*greeks[field][i]
                    aggregate[(context_id, ot)][field] += q*greeks[field][i]
            if rowid is not None:
                row = local_contracts[rowid]
                for field in greeks:
                    row['g_contract_'+field] = float(greeks[field][i]) if np.isfinite(greeks[field][i]) else None
                row['g_contract_abs_delta'] = abs(row['g_contract_delta']) if row['g_contract_delta'] is not None else None
                row['g_contract_gamma_move1pct_over_premium'] = float(.5*greeks['gamma'][i]*(.01*f)**2/p) if p and np.isfinite(greeks['gamma'][i]) else None
        for context_id, cx in enumerate(local_context):
            short = cx['g_CE_short_units']+cx['g_PE_short_units']
            cx['g_model_coverage'] = (total[context_id]-bad[context_id])/total[context_id] if total[context_id] else None
            for side in ('book', 'CE', 'PE'):
                g = aggregate[(context_id, side)]
                for name, value in [('delta_per_short_unit', g['delta']/logs.UNIT[u]/short if short else 0),
                                    ('vega_pct_capital', g['vega_one_point']/CAPITAL*100),
                                    ('theta_pct_capital', g['theta_calendar_day']/CAPITAL*100),
                                    ('gamma_move1pct_pct_capital', .5*g['gamma']*(.01*(cx['g_spot'] or 0))**2/CAPITAL*100)]:
                    cx[f'g_{side}_{name}'] = float(value) if total[context_id] and not bad[context_id] else None
        lookup = {(r['date'], r['clock']): r for r in local_context}
        for row in local_contracts:
            cx = lookup[(row['date'], row['clock'])]
            row.update({k: v for k, v in cx.items() if k.startswith('g_') and k not in row})
        for mode, lots in [('fifo', fifo), ('lifo', lifo)]:
            closed_rows.extend(dict(underlying=u, expiry_date=e, attribution=mode, **row) for row in lots.closes)
        contract_rows.extend(local_contracts)
        context_rows.extend(local_context)
        print('Built side state', u, e, len(local_contracts), flush=True)
    save_records('allocation_contract_features.csv.gz', contract_rows)
    save_records('allocation_greek_context.csv.gz', context_rows)
    save_records('allocation_lot_closures.csv.gz', closed_rows)
    (OUT/'allocation_feature_summary.json').write_text(json.dumps(dict(
        contract_minutes=len(contract_rows), context_minutes=len(context_rows), attributed_close_fragments=len(closed_rows),
        note='Past-known inventory and completed candles; modeled Black Greeks, not broker Greeks. FIFO/LIFO allocation attribution is not original basket identity. OI zero is unavailable. Model coverage is strict over all active legs.'), indent=2)+'\n')


if __name__ == '__main__':
    main()
