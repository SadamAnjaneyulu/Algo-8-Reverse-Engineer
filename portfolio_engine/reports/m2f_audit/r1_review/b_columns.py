"""Task B: which raw columns are time-like, and how do they relate to epoch (col161) vs the SENSEX trade-id ns prefix? [RAW]"""
import csv, re, datetime, collections, json
rows = list(csv.reader(open('/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv', newline='')))
pat = re.compile(r'^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}$')
IST = datetime.timedelta(hours=5, minutes=30)
def parse(s): return (datetime.datetime.strptime(s, '%m/%d/%Y %H:%M') - IST).replace(tzinfo=datetime.timezone.utc).timestamp()  # as UTC epoch
timecols = [j for j in range(167) if sum(1 for r in rows[:2000] if pat.match(r[j])) > 100]
out = {'timelike_cols': timecols}
sens = [(i, r) for i, r in enumerate(rows) if r[12] == 'SENSEX']
res = {}
for j in timecols:
    n = a_ep = a_ns = 0; both = 0; diff = collections.Counter()
    for i, r in sens:
        if not pat.match(r[j]): continue
        t = parse(r[j]); ep = int(r[161]); ns = int(r[28][:19]) / 1e9
        n += 1; a_ep += (t == ep // 60 * 60); a_ns += (t == ns // 60 * 60)
    res[j] = dict(n=n, minute_eq_epoch_minute=a_ep, minute_eq_ns_minute=a_ns)
out['sensex_cols'] = res
# row 8079 time-like cols
r = rows[8079]
out['row8079'] = {j: r[j] for j in timecols}
out['row8079_epoch_minute_ist'] = datetime.datetime.fromtimestamp(int(r[161]) // 60 * 60 + 19800, datetime.timezone.utc).strftime('%H:%M')
out['row8079_ns_minute_ist'] = datetime.datetime.fromtimestamp(int(r[28][:19]) // 10**9 // 60 * 60 + 19800, datetime.timezone.utc).strftime('%H:%M')
# for NIFTY too
nif = [(i, r) for i, r in enumerate(rows) if r[12] == 'NIFTY']
resn = {}
for j in timecols:
    n = a = 0
    for i, r in nif:
        if pat.match(r[j]): n += 1; a += (parse(r[j]) == int(r[161]) // 60 * 60)
    resn[j] = dict(n=n, minute_eq_epoch_minute=a)
out['nifty_cols'] = resn
json.dump(out, open('b_columns_result.json', 'w'), indent=1)
for j in timecols: print(j, 'SENSEX', res[j], 'NIFTY', resn[j])
print(out['row8079'], out['row8079_epoch_minute_ist'], out['row8079_ns_minute_ist'])
