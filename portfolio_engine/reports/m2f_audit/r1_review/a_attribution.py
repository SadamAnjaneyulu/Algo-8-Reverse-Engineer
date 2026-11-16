"""Task A extra: lot-attribution layer (which opening fill each closing fill consumes) under FIFO and LIFO, and realized P&L (FIFO, LIFO, integer paise). Reviewer's own implementation. [RAW]+[IMPL]"""
import collections, json
import rv_replay as R
F = R.load()
def run(policy, method):
    consume = {}; realized = {}
    for iid, L in R.order_fills(F, policy).items():
        pos = 0; lots = collections.deque(); Rz = 0
        for f in L:
            q = f['qty']; s = f['side']
            c = 0 if (pos == 0 or (pos > 0) == (s > 0)) else min(q, abs(pos)); o = q - c; rem = c; used = []
            while rem:
                idx = 0 if method == 'FIFO' else len(lots) - 1
                lr, lq, lpx = lots[idx]; take = min(rem, abs(lq))
                Rz += take * ((f['px'] - lpx) if lq > 0 else (lpx - f['px'])); used.append((lr, take))
                if take == abs(lq): del lots[idx]
                else: lots[idx] = (lr, (abs(lq) - take) * (1 if lq > 0 else -1), lpx)
                rem -= take
            if c: consume[f['row']] = tuple(used)
            if o: lots.append((f['row'], s * o, f['px']))
            pos += s * q
        realized[iid] = Rz
    return consume, realized
out = {}
for m in ('FIFO', 'LIFO'):
    bc, br = run('source_row', m)
    for pol in ('sells_first', 'buys_first', 'trade_id', 'order_no', 'sensex_ns'):
        ac, ar = run(pol, m); ch = [r for r in set(bc) | set(ac) if bc.get(r) != ac.get(r)]
        out[f'{m}|{pol}'] = dict(closing_fills_with_different_source_lots=len(ch), realized_delta_paise=sum(ar.values()) - sum(br.values()), instruments_realized_changed=sum(1 for i in br if br[i] != ar[i]))
json.dump(out, open('a_attribution_result.json', 'w'), indent=1)
for k, v in out.items(): print(k, v)
