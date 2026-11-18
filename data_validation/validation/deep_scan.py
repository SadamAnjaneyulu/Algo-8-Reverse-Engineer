"""Stage 5/7 second pass over every option session: value-plausibility checks that go beyond OHLC consistency.
  spike      - close differs from BOTH neighbours by > 5x in the same direction (isolated bad print), with prices >= 1
  intrinsic  - volume > 0 bar priced below intrinsic value of the same-minute spot by more than 0.5 % of spot (bad price, misalignment or wrong spot)
  oi_jump    - open interest changes by more than 5x between consecutive non-zero values
  oi_zero_vol- bars with volume > 0 and open interest == 0
  post_close - bars after the last regular minute, split by whether they carry volume
  alignment  - option minutes with no spot bar in the same session
Usage: python3 -m validation.deep_scan <commit> <out_dir>"""
import io, json, os, re, sys
from datetime import date
from multiprocessing import Pool
import numpy as np, pandas as pd
from .gitsrc import GitSource
CAS_START = date(2026, 8, 3); _G = None


def _init(commit):
    global _G; _G = GitSource(commit)


def scan(args):
    idx, exp, day = args; D = date.fromisoformat(day); x = pd.read_csv(io.BytesIO(_G.read(f'normalized/{idx}/options/exp{exp}_{day}.csv')))
    out = dict(index=idx, expiry=exp, day=day, rows=len(x), spikes=0, intrinsic_violations=0, oi_jumps=0, oi_zero_with_volume=0, post_close_rows=0, post_close_with_volume=0, spot_missing_minutes=0, intrinsic_checked=0, flat_zero_vol_bars=0)
    if not len(x): return out, []
    x['ts'] = pd.to_datetime(x.datetime); x = x.sort_values(['strike', 'right', 'ts']).reset_index(drop=True); g = x.groupby(['strike', 'right'], sort=False)
    prev, nxt = g.close.shift(1), g.close.shift(-1)
    spike_up = (x.close > 5 * prev) & (x.close > 5 * nxt) & (prev >= 1) & (nxt >= 1); spike_dn = (x.close * 5 < prev) & (x.close * 5 < nxt) & (x.close >= 1)
    sp = spike_up | spike_dn; out['spikes'] = int(sp.sum())
    last = pd.Timestamp(f'{day} 15:39').time() if D >= CAS_START else pd.Timestamp(f'{day} 15:29').time()
    post = x.ts.dt.time > last; out['post_close_rows'] = int(post.sum()); out['post_close_with_volume'] = int((post & (x.volume > 0)).sum())
    oi = x.open_interest.where(x.open_interest > 0); po = oi.groupby([x.strike, x.right]).shift(1); out['oi_jumps'] = int((((oi > 5 * po) | (oi * 5 < po)) & po.notna()).sum()); out['oi_zero_with_volume'] = int(((x.open_interest == 0) & (x.volume > 0)).sum())
    out['flat_zero_vol_bars'] = int(((x.volume == 0) & (x.open == x.high) & (x.high == x.low) & (x.low == x.close)).sum())
    spot = pd.read_csv(io.BytesIO(_G.read(f'normalized/{idx}/underlying/spot/{day}.csv'))); sm = dict(zip(spot.datetime, spot.close))
    S = x.datetime.map(sm); out['spot_missing_minutes'] = int(S.isna().sum())
    reg = (~post) & S.notna() & (x.volume > 0) & (x.volume < 2 ** 31)
    intr = np.where(x.right == 'CE', S - x.strike, x.strike - S); viol = reg & (x.close < intr - 0.005 * S); out['intrinsic_checked'] = int(reg.sum()); out['intrinsic_violations'] = int(viol.sum())
    bad = x[sp | viol].copy(); bad['spot'] = S[sp | viol]; bad['kind'] = np.where(sp[sp | viol], 'spike', 'intrinsic'); bad['index'] = idx; bad['expiry'] = exp; bad['day'] = day
    return out, bad[['index', 'expiry', 'day', 'datetime', 'strike', 'right', 'open', 'high', 'low', 'close', 'volume', 'open_interest', 'spot', 'kind']].head(400).to_dict('records')


def main():
    commit, out_dir = sys.argv[1], sys.argv[2]; g = GitSource(commit); jobs = []
    for p in sorted(g.tree()):
        m = re.match(r'normalized/(nifty|sensex)/options/exp(\S{10})_(\S{10})\.csv', p)
        if m: jobs.append((m[1], m[2], m[3]))
    res, ex = [], []
    with Pool(4, initializer=_init, initargs=(commit,)) as pool:
        for i, (o, b) in enumerate(pool.imap(scan, jobs, chunksize=1)):
            res.append(o); ex += b
            if i % 25 == 0: print(f'{i}/{len(jobs)}', flush=True)
    pd.DataFrame(res).to_csv(os.path.join(out_dir, 'deep_scan_sessions.csv'), index=False); pd.DataFrame(ex).to_csv(os.path.join(out_dir, 'deep_scan_examples.csv'), index=False); print('done')


if __name__ == '__main__': main()
