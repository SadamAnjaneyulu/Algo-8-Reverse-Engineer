"""[RAW] Verify the raw 0-based column semantics claimed by the prior reviewer, from raw content only."""
import sys, os, re, datetime as dt
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import raw_truth as T
raw = T.load_raw(); print('rows', len(raw), 'cols', Counter(len(r) for r in raw))
chk = {}
chk['col11 side in Buy/Sell'] = Counter(r[11] for r in raw)
chk['col27 status'] = Counter(r[27] for r in raw)
# epoch non-decreasing (file order chronological)
ep = [int(r[161]) for r in raw]; chk['epoch backward steps'] = sum(1 for a, b in zip(ep, ep[1:]) if b < a)
# col 161 epoch vs IST wall clock: first fill 2026-06-23 09:16 IST expected by order entry text 9:16
chk['epoch IST vs entry-minute (fill >= entry minute)'] = sum(1 for r in raw if int(r[161]) + T.IST < (dt.datetime.strptime(r[23], '%m/%d/%Y %H:%M') - dt.datetime(1970, 1, 1)).total_seconds() - 1)
chk['fills outside 09:14-15:31 IST'] = sum(1 for e in ep if not (9 * 3600 + 14 * 60 <= (e + T.IST) % 86400 <= 15 * 3600 + 31 * 60))
# price columns
d = [(r[137], r[18]) for r in raw]; chk['col137 != col18 (fill px vs order running-average)'] = sum(1 for a, b in d if abs(float(a) - float(b)) > 1e-9)
chk['col137 on paise grid'] = sum(1 for r in raw if abs(float(r[137]) * 100 - round(float(r[137]) * 100)) > 1e-6)
chk['col137 on 5-paise tick'] = sum(1 for r in raw if abs(float(r[137]) * 100 / 5 - round(float(r[137]) * 100 / 5)) > 1e-6)
chk['px min/max col137 (rupees)'] = (min(float(r[137]) for r in raw), max(float(r[137]) for r in raw))
chk['col33 != col19 (fill qty vs order qty)'] = sum(1 for r in raw if r[33] != r[19])
chk['PartiallyFilled with col33==col19'] = sum(1 for r in raw if r[27] == 'PartiallyFilled' and r[33] == r[19])
chk['Filled with col33!=col19'] = sum(1 for r in raw if r[27] == 'Filled' and r[33] != r[19])
# lot multiples
chk['NIFTY qty %65'] = Counter(int(r[33]) % 65 == 0 for r in raw if r[12] == 'NIFTY'); chk['SENSEX qty %20'] = Counter(int(r[33]) % 20 == 0 for r in raw if r[12] == 'SENSEX')
# parent prefixes
chk['col163 prefix'] = Counter((re.match(r'^([a-z]+_)', r[163]).group(1) if re.match(r'^([a-z]+_)', r[163]) else 'num') for r in raw)
chk['underlyings'] = Counter(r[12] for r in raw)
chk['expiry col vs col15 day-of-week'] = Counter(dt.datetime.strptime(r[15], '%m/%d/%Y %H:%M').strftime('%a') for r in raw if r[12] == 'NIFTY'), Counter(dt.datetime.strptime(r[15], '%m/%d/%Y %H:%M').strftime('%a') for r in raw if r[12] == 'SENSEX')
for k, v in chk.items(): print(k, '->', v)
# order-entry-time semantics: col 23 text vs UTC; is it before first fill of the parent?
print('parent consistency: entry text constant per parent:', all(len({r[23] for r in raw if r[163] == p}) == 1 for p in list({r[163] for r in raw})[:300]))
