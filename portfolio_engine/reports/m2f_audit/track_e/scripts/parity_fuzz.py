"""Track E independent Python<->C++ parity harness (writes only under --work).
usage: parity_fuzz.py --root <scratch tree containing portfolio_engine/> --work <dir> [--n 240] [--real]
Own sequence generator (NOT the repo's synthetic generators), own comparison (byte-for-byte), own exact-arithmetic reference ([IMPL]) for FIFO/LIFO/AVG.
Classes: python-vs-cpp byte parity = [XLANG] (the two engines share one specification written by the same author); reference-vs-python = [IMPL]."""
import argparse, json, os, random, subprocess, sys, itertools
from fractions import Fraction
ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--work', required=True); ap.add_argument('--n', type=int, default=240); ap.add_argument('--real', action='store_true'); ap.add_argument('--seed0', type=int, default=1000)
a = ap.parse_args(); PE = os.path.join(a.root, 'portfolio_engine'); sys.path.insert(0, os.path.join(PE, 'python'))
from pe import tsvio, replay as rp
from pe.schema import *
BIN = os.path.join(PE, 'build', 'pe_replay'); os.makedirs(a.work, exist_ok=True)
MODE = 'SYNTHETIC_TEST'; BASE = days_from_civil(2026, 3, 2) * 86400 - IST_OFFSET_S + 9 * 3600


def mk_ins(und, expiry, cp, strike):
    return Instrument(f'{und}|{expiry}|{cp}|{strike}', und, 'NSEFO', 'OPTION', cp, strike, expiry, 65 if und == 'NIFTY' else 20, TICK_PAISE, 'AUDIT_E')


def gen(seed, profile):
    r = random.Random(seed); ins = {}; fills = []
    unds = ['NIFTY'] if profile in (0, 1) else ['NIFTY', 'SENSEX']
    exps = ['2026-03-05', '2026-03-12', '2026-04-02']
    for u in unds:
        for e in exps[: (3 if profile >= 3 else 1)]:
            for cp in ('CE', 'PE'):
                for k in range(2 if profile < 3 else 3): i = mk_ins(u, e, cp, 20000 + 100 * k); ins[i.instrument_id] = i
    ids = sorted(ins); n = {0: 120, 1: 100, 2: 150, 3: 200, 4: 80, 5: 150, 6: 12}[profile]; t = 0; cur = {}
    for k in range(n):
        if profile == 2: t += r.choice((0, 0, 0, 1))                      # lots of same-second fills
        elif profile == 3: t += r.choice((0, 5, 3600, 30000, 86400 // 2))  # cross IST midnight, multi-day
        else: t += r.randint(0, 40)
        iid = r.choice(ids if profile != 0 else ids[:1]); inv = cur.get(iid, 0)
        if profile == 0: side = (-1 if inv > 0 else 1) if r.random() < 0.8 else r.choice((-1, 1)); q = r.choice((1, 65, 130, 195, 1000))           # reversal heavy
        elif profile == 1: side = (-1 if inv > 0 else 1) if inv != 0 and r.random() < 0.6 else (1 if inv <= 0 and r.random() < 0.5 else -1); q = r.choice((1, 3, 65, 65, 130))
        elif profile == 4: side = r.choice((-1, 1)); q = r.choice((1, 2, 10**9, 10**9 + 7, 123456789, 65))
        elif profile == 6: side = r.choice((-1, 1)); q = r.choice((2 * 10**9, 3 * 10**9)); 
        else: side = r.choice((-1, 1)); q = r.choice((1, 65, 130, 20, 40, 65 * 7))
        if profile == 4: px = r.choice((5, 10, 5 * 20, 5 * 4000, 5 * 10**7, 5 * 10**8))
        elif profile == 6: px = r.choice((3 * 10**9, 5 * 10**8 * 6))
        else: px = 5 * r.randint(1, 6000)
        cur[iid] = inv + side * q
        dup = profile in (5, 2) and r.random() < 0.05
        fills.append(Fill(f'A{k:06d}', k + 1, f'P{r.randint(0, n // 3) if profile in (2, 5) else k}', r.choice(('num', 'h_', 's_')), iid, BASE + t, side, q, px, q * (3 if r.random() < 0.2 else 1) if profile in (5,) else q,
                          'PartiallyFilled' if profile == 5 and r.random() < 0.3 else 'Filled', dup, MODE, f'auditE:{profile}:{seed}'))
    if profile == 5 and r.random() < 2:                                       # out-of-order input (shuffle part of the file order, keep source_row ids)
        r.shuffle(fills)
    return ins, fills


def write(ins, fills, tag):
    ev = os.path.join(a.work, f'{tag}_events.tsv'); ip = os.path.join(a.work, f'{tag}_instruments.tsv'); tsvio.write_events(ev, fills); tsvio.write_instruments(ip, ins); return ev, ip


def cpp(ev, ip, method, tie, interval, tag):
    d = os.path.join(a.work, f'{tag}_{method}_{tie}'); os.makedirs(d, exist_ok=True)
    r = subprocess.run([BIN, '--events', ev, '--instruments', ip, '--mode', MODE, '--method', method, '--tie', tie, '--snapshot-interval', str(interval), '--dump', d + '/dump.tsv', '--roles', d + '/roles.tsv', '--lineage-dir', d, '--strict'], capture_output=True, text=True)
    if r.returncode: return None, r.stderr.strip()
    return {n: open(os.path.join(d, n), 'rb').read() for n in os.listdir(d)}, None


def ref(fills, ins, method, tie):
    """[IMPL] independent exact-arithmetic reference: per-instrument position with a plain list of lots, Fractions for AVG. Returns realized, cash, per-instrument inventory, reversals."""
    tk = {'src': lambda s: 0, 'sells_first': lambda s: 0 if s < 0 else 1, 'buys_first': lambda s: 0 if s > 0 else 1}[tie]
    seq = sorted([f for f in fills if not f.is_duplicate_fill], key=lambda f: (f.timestamp_s, tk(f.side), f.source_row_id, f.fill_id))
    lots = {}; avg = {}; realized = Fraction(0); cash = 0; rev = 0; inv = {}; opened = 0; closed = 0
    for f in seq:
        L = lots.setdefault(f.instrument_id, []); signed = sum(s * q for s, q, _ in L) if method != 'AVG' else inv.get(f.instrument_id, 0)
        q = f.quantity; cash += -f.side * q * f.price_paise
        if signed != 0 and (signed > 0) != (f.side > 0):                              # against the inventory
            cq = min(q, abs(signed)); direction = 1 if signed > 0 else -1
            if method == 'AVG':
                realized += direction * (Fraction(f.price_paise) - avg[f.instrument_id]) * cq; inv[f.instrument_id] = signed - direction * cq
                if inv[f.instrument_id] == 0: avg.pop(f.instrument_id)
            else:
                need = cq
                while need:
                    j = 0 if method == 'FIFO' else -1; s_, lq, lp = L[j]; take = min(need, lq); realized += direction * (f.price_paise - lp) * take; need -= take
                    if take == lq: L.pop(j)
                    else: L[j] = (s_, lq - take, lp)
            closed += cq; rest = q - cq
            if rest: rev += 1
        else: rest = q
        if rest:
            if method == 'AVG':
                old = abs(inv.get(f.instrument_id, 0)); op = avg.get(f.instrument_id, Fraction(0)); avg[f.instrument_id] = (op * old + f.price_paise * rest) / (old + rest); inv[f.instrument_id] = inv.get(f.instrument_id, 0) + f.side * rest
            else: L.append((f.side, rest, f.price_paise))
            opened += rest
    if method != 'AVG': inv = {i: sum(s * q for s, q, _ in L) for i, L in lots.items()}
    return dict(realized=realized, cash=cash, inv={k: v for k, v in inv.items()}, reversal_fills=rev, opened=opened, closed=closed)


def dump_totals(dump):
    T = {}; I = {}
    for l in dump.splitlines():
        t = l.split('\t')
        if t[0] == 'TOTAL': T[t[1]] = t[2]
        if t[0] == 'INSTR': I[t[1]] = int(t[2])
    return T, I


res = dict(cases=0, byte_identical=0, differ=[], cpp_rejected_py_accepted=[], py_rejected=[], ref_checked=0, ref_mismatch=[], by_profile={})
seeds = [(a.seed0 + s, s % 7) for s in range(a.n)]
for seed, profile in seeds:
    ins, fills = gen(seed, profile); tag = f's{seed}p{profile}'; ev, ip = write(ins, fills, tag)
    for method, tie in itertools.product(METHODS, TIE_ORDERS):
        if tie != 'src' and (seed % 3): continue                                   # all ties on every third seed, 'src' on all
        interval = (seed % 4) * 7; res['cases'] += 1; bp = res['by_profile'].setdefault(profile, dict(cases=0, identical=0))
        bp['cases'] += 1
        try:
            fl = tsvio.read_events(ev, tsvio.read_instruments(ip)); R = rp.replay(fl, ins, MODE, method, tie, interval, True, True); pyfiles = {'dump.tsv': R.dump.encode(), 'roles.tsv': rp.roles_tsv(R.roles).encode(), **{k: v.encode() for k, v in rp.lineage_files(R).items()}}
        except Exception as e:
            res['py_rejected'].append(dict(seed=seed, profile=profile, method=method, tie=tie, err=f'{type(e).__name__}: {e}'[:200]))
            cf, err = cpp(ev, ip, method, tie, interval, tag); res['py_rejected'][-1]['cpp_also_rejected'] = cf is None; res['py_rejected'][-1]['cpp_err'] = (err or '')[:120]
            continue
        cf, err = cpp(ev, ip, method, tie, interval, tag)
        if cf is None: res['cpp_rejected_py_accepted'].append(dict(seed=seed, profile=profile, method=method, tie=tie, err=err[:200])); continue
        bad = [n for n in pyfiles if cf.get(n) != pyfiles[n]]
        if not bad: res['byte_identical'] += 1; bp['identical'] += 1
        else:
            res['differ'].append(dict(seed=seed, profile=profile, method=method, tie=tie, files=bad))
        if profile != 6:
            ref_r = ref(fl, ins, method, tie); T, I = dump_totals(R.dump); res['ref_checked'] += 1; ok = True
            rp_ = Fraction(T['realized_pnl_paise']) if method != 'AVG' else Fraction(float(T['realized_pnl_paise']))
            tol = 0 if method != 'AVG' else max(Fraction(1, 1000), abs(ref_r['realized']) * Fraction(1, 10**9))
            ok &= abs(rp_ - ref_r['realized']) <= tol and int(T['cash_flow_paise']) == ref_r['cash'] and int(T['reversal_fills']) == ref_r['reversal_fills'] and int(T['opened_units']) == ref_r['opened'] and int(T['closed_units']) == ref_r['closed']
            ok &= all(I.get(k, 0) == v for k, v in ref_r['inv'].items()) and all(v == ref_r['inv'].get(k, 0) for k, v in I.items())
            if not ok: res['ref_mismatch'].append(dict(seed=seed, profile=profile, method=method, tie=tie, py=T['realized_pnl_paise'], ref=str(float(ref_r['realized']))))
res['summary'] = dict(cases=res['cases'], byte_identical=res['byte_identical'], differ=len(res['differ']), cpp_rejected_py_accepted=len(res['cpp_rejected_py_accepted']), py_rejected=len(res['py_rejected']), ref_checked=res['ref_checked'], ref_mismatch=len(res['ref_mismatch']), sequences=len(seeds))
json.dump(res, open(os.path.join(a.work, 'parity_fuzz_result.json'), 'w'), indent=1, default=str); print(json.dumps(res['summary'])); print(json.dumps(res['by_profile']))
for k in ('differ', 'cpp_rejected_py_accepted', 'py_rejected', 'ref_mismatch'):
    for x in res[k][:6]: print(k, x)
