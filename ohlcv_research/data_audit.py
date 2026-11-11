"""PHASE 0 - data audit of the Breeze OHLCV files and their link to the Algo 8 ledger.  Read-only; no modelling.
python3 ohlcv_research/data_audit.py  -> results/audit_*.csv and results/data_audit_report.txt"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from common import *

def grid_stats(g, ts='ts'):
    t = g[ts]; sec = (t - t.dt.normalize()).dt.total_seconds()
    return pd.Series(dict(bars=len(g), dup=int(t.duplicated().sum()), first=t.min().strftime('%H:%M'), last=t.max().strftime('%H:%M'),
                          off_session=int(((sec < 9 * 3600 + 15 * 60) | (sec > 15 * 3600 + 29 * 60)).sum()), not_on_minute=int((sec % 60 != 0).sum())))

if __name__ == '__main__':
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
    R = []; P = lambda *a: R.append(' '.join(str(x) for x in a))
    # ---------------- index ------------------------------------------------------------------------------------------------------------------------------
    I = load_index(with_files=True); I['date'] = I.ts.dt.normalize()
    P('INDEX rows', len(I), '| tz offsets', I.tz.value_counts().to_dict(), '| files', I.file.nunique(), '| files per (und, date) max', int(I.groupby(['und', 'date']).file.nunique().max()))
    P('provider_volume non-zero rows:', int((I.provider_volume != 0).sum()))
    gi = I.groupby(['und', 'date']).apply(grid_stats).reset_index(); gi['missing'] = SESSION_BARS - (gi.bars - gi.dup)
    P('index sessions per underlying:', gi.groupby('und').size().to_dict(), '| date range', I.date.min().date(), I.date.max().date())
    P('index bars per session:', gi.bars.describe()[['min', '50%', 'max']].to_dict(), '| sessions with missing minutes:', int((gi.missing > 0).sum()), '| total missing minutes:', int(gi.missing.clip(lower=0).sum()),
      '| duplicate timestamps:', int(gi.dup.sum()), '| off-session bars:', int(gi.off_session.sum()))
    P(gi[gi.missing != 0].to_string(index=False) if (gi.missing != 0).any() else 'every index session has exactly 375 bars 09:15-15:29')
    bad = (I.high < I[['open', 'close']].max(axis=1)) | (I.low > I[['open', 'close']].min(axis=1)) | (I[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
    P('index OHLC inconsistent rows:', int(bad.sum()), '| zero-range bars share:', round(float((I.high == I.low).mean()), 4))
    sd = {u: set(g.date) for u, g in I.groupby('und')}; P('sessions only in NIFTY:', sorted(d.date() for d in sd['NIFTY'] - sd['SENSEX']), '| only in SENSEX:', sorted(d.date() for d in sd['SENSEX'] - sd['NIFTY']))
    wk = pd.Series(sorted(sd['NIFTY'])); P('NIFTY weekday counts:', wk.dt.day_name().value_counts().to_dict(), '| weekdays absent between first and last session:',
                                              [d.date() for d in pd.bdate_range(wk.min(), wk.max()) if d not in sd['NIFTY']])
    gi.to_csv(os.path.join(RES, 'audit_index_sessions.csv'), index=False)
    # ---------------- options ----------------------------------------------------------------------------------------------------------------------------
    O = load_options(with_files=True); O['date'] = O.ts.dt.normalize(); O['dte'] = (O.expiry - O.date).dt.days
    key = ['und', 'expiry', 'strike', 'cp', 'date']
    P('\nOPTION rows', len(O), '| tz offsets', O.tz.value_counts().to_dict(), '| files', O.file.nunique(), '| contract-days', O.groupby(key).ngroups, '| files per contract-day max', int(O.groupby(key).file.nunique().max()))
    P('duplicate (contract, ts) rows:', int(O.duplicated(['und', 'expiry', 'strike', 'cp', 'ts']).sum()))
    sec = (O.ts - O.date).dt.total_seconds(); P('off-session option bars:', int(((sec < 9 * 3600 + 15 * 60) | (sec > 15 * 3600 + 29 * 60)).sum()), '| not on a minute:', int((sec % 60 != 0).sum()))
    bad = (O.high < O[['open', 'close']].max(axis=1)) | (O.low > O[['open', 'close']].min(axis=1)) | (O[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
    P('option OHLC inconsistent rows:', int(bad.sum()), '| price not on 0.05 tick (close):', int((np.abs(O.close * 20 - np.round(O.close * 20)) > 1e-6).sum()))
    P('volume: negative', int((O.volume < 0).sum()), '| zero', int((O.volume == 0).sum()), f'({(O.volume == 0).mean():.2%})', '| non-integer', int((O.volume % 1 != 0).sum()),
      '| multiple of lot size (NIFTY 65 / SENSEX 20):', {u: round(float((g.volume % LOT[u] == 0).mean()), 4) for u, g in O.groupby('und')})
    cd = O.groupby(key).agg(bars=('ts', 'size'), first=('ts', 'min'), last=('ts', 'max'), vol=('volume', 'sum'), dte=('dte', 'first')).reset_index()
    cd['coverage'] = cd.bars / SESSION_BARS
    P('contract-days by underlying and dte:'); P(cd.groupby(['und', 'dte']).agg(contract_days=('bars', 'size'), median_bars=('bars', 'median'), mean_coverage=('coverage', 'mean'), full_375=('bars', lambda x: (x == 375).mean())).round(3).to_string())
    P('expiries:', {u: sorted(str(e.date()) for e in g.expiry.unique()) for u, g in O.groupby('und')})
    P('expiry weekday:', {u: pd.Series(g.expiry.unique()).dt.day_name().value_counts().to_dict() for u, g in O.groupby('und')})
    P('strike step check (share of strikes on the step grid):', {u: round(float((g.strike % STEP[u] == 0).mean()), 4) for u, g in O.groupby('und')})
    # gaps (stale-price risk): minutes since the previous bar of the same contract-day
    O = O.sort_values(key + ['ts']); gap = O.groupby(key).ts.diff().dt.total_seconds() / 60
    P('gap between consecutive bars of a contract-day (minutes): share == 1:', round(float((gap == 1).mean()), 4), '| > 5:', round(float((gap > 5).mean()), 5), '| > 30:', round(float((gap > 30).mean()), 6), '| max:', gap.max())
    cd.to_csv(os.path.join(RES, 'audit_option_contract_days.csv'), index=False)
    # moneyness of each contract-day vs the index (strike steps from the session's first index close) and coverage by moneyness
    ix = load_index(); io = ix.assign(date=ix.ts.dt.normalize()).groupby(['und', 'date']).close.first().rename('s_open').reset_index()
    cd = cd.merge(io, on=['und', 'date'], how='left'); cd['otm_steps'] = np.where(cd.cp == 'CE', cd.strike - cd.s_open, cd.s_open - cd.strike) / cd.und.map(STEP)
    cd['mny'] = pd.cut(cd.otm_steps, [-1e9, -3, -1, 1, 3, 10, 1e9], labels=['ITM > 3', 'ITM 1-3', 'ATM +-1', 'OTM 1-3', 'OTM 3-10', 'OTM > 10 (wings)'])
    P('coverage by moneyness at the session open:'); P(cd.groupby(['und', 'mny'], observed=True).agg(contract_days=('bars', 'size'), mean_coverage=('coverage', 'mean'), median_bars=('bars', 'median')).round(3).to_string())
    P('contract-days without an index session:', int(cd.s_open.isna().sum()))
    # ---------------- ledger <-> market mapping -----------------------------------------------------------------------------------------------------------
    o = load_orders(); o['date'] = pd.to_datetime(o.date); have = set(map(tuple, cd[key].values.tolist()))
    o['has_candles'] = [(u, e, k, c, d) in have for u, e, k, c, d in zip(o.und, o.expiry, o.strike, o.cp, o.date)]
    P('\nLEDGER orders', len(o), '| cycles', o.groupby(['und', 'expiry']).ngroups, '| trade dates', o.date.nunique(), '| orders whose contract-day has candles:', round(float(o.has_candles.mean()), 4),
      '| lots:', round(float((o.lots * o.has_candles).sum() / o.lots.sum()), 4))
    P('orders without candles by module:', o[~o.has_candles].tp.value_counts().to_dict())
    td = o.groupby(['und', 'date']).size().reset_index()[['und', 'date']]; isess = set(map(tuple, gi[['und', 'date']].values.tolist()))
    P('ledger (und, date) sessions:', len(td), '| with index bars:', sum((u, d) in isess for u, d in zip(td.und, td.date)))
    lc = set(map(tuple, o[key].drop_duplicates().values.tolist())); P('contract-days in market data that Algo 8 did NOT trade that day:', len(have - lc), 'of', len(have), '| traded contract-days:', len(lc))
    # previous-completed-bar staleness at each order's decision minute
    Ob = O[['und', 'expiry', 'strike', 'cp', 'ts']].copy(); Ob['bar_end'] = Ob.ts + pd.Timedelta(minutes=1)
    q = o[['oid', 'und', 'expiry', 'strike', 'cp', 't_dec_lo', 'tp', 'label']].copy(); q['dm'] = pd.to_datetime(q.t_dec_lo).dt.floor('min')
    m = pd.merge_asof(q.sort_values('dm'), Ob.sort_values('bar_end'), left_on='dm', right_on='bar_end', by=['und', 'expiry', 'strike', 'cp'], direction='backward')
    m['same_day'] = m.bar_end.dt.normalize() == m.dm.dt.normalize(); age = ((m.dm - m.bar_end).dt.total_seconds() / 60).where(m.same_day)
    P('age (minutes) of the last COMPLETED bar of the traded contract at the decision minute: none that day', round(float(age.isna().mean()), 4), '| 0 (bar ended at the decision minute)', round(float((age == 0).mean()), 4),
      '| <= 5', round(float((age <= 5).mean()), 4), '| > 15', round(float((age > 15).mean()), 4))
    m['age'] = age; m['mod'] = np.where(m.tp == 'num', 'body', np.where(m.tp == 'h_', 'wing', 'other'))
    P(m.groupby('mod').age.agg(n='size', none=lambda x: x.isna().mean(), fresh=lambda x: (x == 0).mean(), le5=lambda x: (x <= 5).mean(), gt15=lambda x: (x > 15).mean()).round(4).to_string())
    # ---------------- bar-label convention: are bars labelled by their START? -------------------------------------------------------------------------------
    f = load_fills(); f['m0'] = f.t.dt.floor('min'); Ok = O.set_index(['und', 'expiry', 'strike', 'cp', 'ts'])[['low', 'high', 'volume']]
    out = {}
    for name, sh in (('bar labelled floor(fill minute)  [bar START convention]', 0), ('bar labelled fill minute + 1   [bar END convention]', 1), ('bar labelled fill minute - 1', -1)):
        idx = pd.MultiIndex.from_arrays([f.und, f.expiry, f.strike, f.cp, f.m0 + pd.Timedelta(minutes=sh)]); b = Ok.reindex(idx)
        ins = (f.px_fill.values >= b.low.values - 1e-9) & (f.px_fill.values <= b.high.values + 1e-9); out[name] = (float(np.isfinite(b.low.values).mean()), float(ins[np.isfinite(b.low.values)].mean()))
    P('\nBAR LABEL CHECK - share of Algo 8 fills whose price lies inside [low, high] of the candidate bar (bar exists share, inside share):')
    for k, v in out.items(): P('  ', k, '->', round(v[0], 4), round(v[1], 4))
    idx = pd.MultiIndex.from_arrays([f.und, f.expiry, f.strike, f.cp, f.m0]); b = Ok.reindex(idx)
    fq = f.assign(bv=b.volume.values).groupby(['und', 'expiry', 'strike', 'cp', 'm0']).agg(q=('qty_fill', 'sum'), bv=('bv', 'first')).dropna()
    P('VOLUME CHECK - contract-minutes with Algo 8 fills:', len(fq), '| bar volume >= Algo 8 filled quantity:', round(float((fq.bv >= fq.q).mean()), 4), '| bar volume == 0 although Algo 8 traded:', int((fq.bv == 0).sum()))
    # ---------------- CE / PE pair availability ---------------------------------------------------------------------------------------------------------------
    W = O.pivot_table(index=['und', 'expiry', 'strike', 'ts'], columns='cp', values='close', aggfunc='last')
    P('\nPAIRS - (contract-strike, minute) rows:', len(W), '| CE and PE both printed that minute:', round(float(W.notna().all(axis=1).mean()), 4))
    ixm = ix.set_index(['und', 'ts']).close; rows = []
    for (u, e), g in O.groupby(['und', 'expiry']):
        for d, gd in g.groupby('date'):
            s = ixm.loc[u].reindex(pd.date_range(d + SESSION_OPEN, periods=SESSION_BARS, freq='min'))
            if s.isna().all(): continue
            atm = (np.round(s.shift(1) / STEP[u]) * STEP[u])                       # ATM from the previous completed index bar
            pv = gd.pivot_table(index='ts', columns=['strike', 'cp'], values='close', aggfunc='last')
            okc = okp = both = both5 = n = 0
            pvf = pv.reindex(s.index); last = pvf.notna().astype(int); recent = last.rolling(5, min_periods=1).max()
            for t, a in atm.dropna().items():
                n += 1; c = (a, 'CE') in pvf.columns and bool(last.at[t, (a, 'CE')]); p = (a, 'PE') in pvf.columns and bool(last.at[t, (a, 'PE')])
                c5 = (a, 'CE') in pvf.columns and bool(recent.at[t, (a, 'CE')]); p5 = (a, 'PE') in pvf.columns and bool(recent.at[t, (a, 'PE')])
                okc += c; okp += p; both += c and p; both5 += c5 and p5
            rows.append(dict(und=u, expiry=e, date=d, dte=(e - d).days, minutes=n, atm_ce=okc / n, atm_pe=okp / n, atm_both=both / n, atm_both_within5=both5 / n, strikes=gd.strike.nunique(), contracts=gd.groupby(['strike', 'cp']).ngroups))
    PA = pd.DataFrame(rows); PA.to_csv(os.path.join(RES, 'audit_atm_pair_coverage.csv'), index=False)
    P('ATM straddle (nearest strike to the previous index close) availability per session-expiry, by dte:')
    P(PA.groupby(['und', 'dte']).agg(session_expiries=('minutes', 'size'), strikes=('strikes', 'median'), atm_both_same_minute=('atm_both', 'mean'), atm_both_within_5min=('atm_both_within5', 'mean'), worst=('atm_both_within5', 'min')).round(3).to_string())
    P('sessions with option data per underlying:', PA.groupby('und').date.nunique().to_dict(), '| index sessions with NO option data:', {u: len(sd[u] - set(PA[PA.und == u].date)) for u in sd})
    open(os.path.join(RES, 'data_audit_report.txt'), 'w').write('\n'.join(R) + '\n'); print('\n'.join(R))
