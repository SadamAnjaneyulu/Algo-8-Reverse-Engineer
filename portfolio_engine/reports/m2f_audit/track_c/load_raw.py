"""Load fills from the RAW csv (no header, 167 cols).  Verified columns (see FINDINGS.md): 4 order no, 11 side, 12 und, 14 strike, 15 expiry (date part), 16 CE/PE, 19 order qty, 23 order-entry minute (IST wall clock),
27 status, 33 fill qty (units), 137 fill px rupees, 161 UTC epoch, 163 parent id (prefix h_/s_/v_/m_ else numeric => 'num'), 166 app key string (last 6 chars = key id)."""
import csv, datetime as dt
RAW = '/home/user/Algo-8-Reverse-Engineer/Trades_GKOHNP140.csv'
IST = 19800


def load(path=RAW):
    out = []
    with open(path, newline='') as fh:
        for row, r in enumerate(csv.reader(fh)):
            exp = dt.datetime.strptime(r[15], '%m/%d/%Y %H:%M').date().isoformat()
            tag = r[163][:2] if r[163][:2] in ('h_', 's_', 'v_', 'm_') else 'num'
            e = dt.datetime.strptime(r[23], '%m/%d/%Y %H:%M'); emin = int((e - dt.datetime(1970, 1, 1)).total_seconds()) - IST
            out.append(dict(row=row, ts=int(r[161]), inst=(r[12], exp, r[16], int(r[14])), sgn=1 if r[11] == 'Buy' else -1, qty=int(r[33]), px=round(float(r[137]) * 100), parent=r[163], tag=tag, emin=emin, app=r[166][-6:], order_no=r[4], status=r[27], ordqty=int(r[19]), oavg=r[18]))
    return out
