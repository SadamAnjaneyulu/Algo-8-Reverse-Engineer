"""Scenario file (tab separated, '#' comment lines, pure printable ASCII, '\\n' line ends). Every scenario must declare META evidence SYNTHETIC_TEST_ONLY.

META  key value                 INST  instrument_id lot_size           RISK  key value
PLUGIN name version enabled     (registration = evaluation order)      CONFIG plugin key value
LEG   fill_id basket leg instrument side qty price_paise ts            (the seed fills that create a basket)
MARK  ts instrument price_paise TICK  ts                                (ticks = the ONLY times at which plugins are evaluated)
ACTION ts action_id plugin version type basket leg qty parent_cut_id info_ts group_id   (offered to the scripted_actions plugin at exactly `ts`, which must be a TICK time)

Input rules (identical in the C++ loader; a violation is an error, never a silent repair):
  integers: optional '-' then ASCII digits only; every field has a range (timestamps 0..1e11, prices 5..1e9 and a multiple of 5, quantities 1..1e7 and a multiple of the lot, lot 1..1e6, ACTION qty +-1e12, RISK values 0..1e12)
  ids: basket/leg/fill ids [A-Za-z0-9_.:-]{1,64} ('|' is not allowed), action ids also allow '|'; the fill ids PC<digits> belong to the engine; instruments UNDERLYING|YYYY-MM-DD|CE-or-PE|strike
  META, INST, RISK, CONFIG, PLUGIN keys may appear once; CONFIG may only name a registered plugin; META evidence must appear exactly once
Canonical order inside the file never changes a result: LEG/MARK/TICK/ACTION lines are sorted after loading."""
import re
from . import EVIDENCE

MAXT = 10 ** 11; MAXPX = 10 ** 9; MAXQTY = 10 ** 7; MAXLOT = 10 ** 6; MAXACTQTY = 10 ** 12


class ScenarioError(Exception): pass


_INT = re.compile(r'-?[0-9]+\Z')
_ID = re.compile(r'[A-Za-z0-9_.:-]{1,64}\Z'); _AID = re.compile(r'[A-Za-z0-9_.:|-]{1,300}\Z'); _NAME = re.compile(r'[a-z][a-z0-9_]{0,40}\Z'); _KEY = re.compile(r'[a-z_]{1,40}\Z'); _VAL = re.compile(r'[A-Za-z0-9_.*:-]{0,64}\Z')
_SEMVER = re.compile(r'[0-9]{1,40}\.[0-9]{1,40}\.[0-9]{1,40}\Z'); _TYPE = re.compile(r'[A-Z_]{1,20}\Z'); _FILLID = re.compile(r'PC[0-9]+\Z')
_INSTR = re.compile(r'([A-Z]{1,12})\|([0-9]{4})-([0-9]{2})-([0-9]{2})\|(CE|PE)\|([0-9]{1,9})\Z')


def to_int(x, what, lo, hi):
    if not _INT.match(x) or len(x) > 20: raise ScenarioError(f'{what}: not a valid integer: {x!r}')
    v = int(x)
    if v < lo or v > hi: raise ScenarioError(f'{what}: {v} outside {lo}..{hi}')
    return v


def need(rx, x, what):
    if not rx.match(x): raise ScenarioError(f'{what}: invalid value {x!r}')
    return x


def _group(p):
    g = p[11] if len(p) > 11 else ''
    return g if g == '' else need(_ID, g, 'group id')


def check_instrument_id(iid):
    m = _INSTR.match(iid)
    if not m or not (1 <= int(m.group(3)) <= 12) or not (1 <= int(m.group(4)) <= 31): raise ScenarioError(f'invalid instrument id {iid!r}')


def check_text(text):
    for ch in text:
        o = ord(ch)
        if o > 126 or (o < 32 and ch not in '\n\t'): raise ScenarioError(f'scenario files must be printable ASCII (found code {o})')


class Scenario:
    def __init__(self):
        self.name = ''; self.description = ''; self.method = 'FIFO'; self.instruments = {}; self.risk = {}; self.plugins = []; self.configs = {}
        self.seeds = []; self.marks = []; self.ticks = []; self.actions = []; self.duplicates = []          # duplicates: identical repeated LEG events (ignored, counted)

    @staticmethod
    def action_key(a): return (a['ts'], a['action_id'], a['plugin'], a['version'], a['type'], a['basket_id'], a['leg_id'], a['qty'], a['parent_cut_id'], a['info_ts'], a['group_id'])

    @property
    def duplicate_seeds(self): return len(self.duplicates)

    @staticmethod
    def load(path):
        raw = open(path, 'rb').read()
        try: text = raw.decode('ascii')
        except UnicodeDecodeError: raise ScenarioError('scenario files must be printable ASCII')
        return Scenario.parse(text)

    @staticmethod
    def parse(text):
        check_text(text); s = Scenario(); meta = {}; seen_fill = {}; legdef = {}; markpx = {}; seen_inst = set(); seen_cfg = set(); seen_plugin = set()
        for n, line in enumerate(text.split('\n'), 1):
            if line == '' or line.startswith('#'): continue
            p = line.split('\t'); k = p[0]; w = f'line {n}'
            try:
                if k == 'META':
                    key = need(_KEY, p[1], w)
                    if key in meta: raise ScenarioError(f'{w}: META {key} repeated')
                    meta[key] = p[2] if len(p) > 2 else ''
                elif k == 'INST':
                    check_instrument_id(p[1])
                    if p[1] in s.instruments: raise ScenarioError(f'{w}: instrument {p[1]} repeated')
                    s.instruments[p[1]] = to_int(p[2], w, 1, MAXLOT)
                elif k == 'RISK':
                    if p[1] in s.risk: raise ScenarioError(f'{w}: RISK {p[1]} repeated')
                    s.risk[p[1]] = to_int(p[2], w, 0, 10 ** 12)
                elif k == 'PLUGIN':
                    name = need(_NAME, p[1], w); need(_SEMVER, p[2], w)
                    if name in seen_plugin: raise ScenarioError(f'{w}: plugin {name} listed twice')
                    if p[3] not in ('0', '1'): raise ScenarioError(f'{w}: enabled flag must be 0 or 1')
                    seen_plugin.add(name); s.plugins.append((name, p[2], p[3] == '1'))
                elif k == 'CONFIG':
                    key = (need(_NAME, p[1], w), need(_KEY, p[2], w))
                    if key in seen_cfg: raise ScenarioError(f'{w}: CONFIG {key} repeated')
                    seen_cfg.add(key); s.configs.setdefault(key[0], {})[key[1]] = need(_VAL, p[3], w)
                elif k == 'LEG':
                    d = dict(fill_id=need(_ID, p[1], w), basket_id=need(_ID, p[2], w), leg_id=need(_ID, p[3], w), instrument_id=p[4], side=to_int(p[5], w, -1, 1), qty=to_int(p[6], w, 1, MAXQTY), price=to_int(p[7], w, 5, MAXPX), ts=to_int(p[8], w, 0, MAXT))
                    if _FILLID.match(d['fill_id']): raise ScenarioError(f'{w}: fill ids PC<digits> are reserved for the engine')
                    if d['fill_id'] in seen_fill:
                        if seen_fill[d['fill_id']] != d: raise ScenarioError(f'{w}: fill_id {d["fill_id"]} repeated with different content')
                        s.duplicates.append(d); continue                       # an identical repeat is a duplicate event: ignored and counted
                    seen_fill[d['fill_id']] = d; s.seeds.append(d)
                elif k == 'MARK':
                    key = (to_int(p[1], w, 0, MAXT), p[2]); px = to_int(p[3], w, 5, MAXPX)
                    if key in markpx and markpx[key] != px: raise ScenarioError(f'{w}: conflicting marks for {key}')
                    if key not in markpx: markpx[key] = px; s.marks.append((key[0], key[1], px))
                elif k == 'TICK': s.ticks.append(to_int(p[1], w, 0, MAXT))
                elif k == 'ACTION':
                    ts = to_int(p[1], w, 0, MAXT)
                    s.actions.append(dict(ts=ts, action_id=need(_AID, p[2], w), plugin=p[3] if p[3] == '' else need(_NAME, p[3], w), version=p[4] if p[4] == '' else need(_SEMVER, p[4], w), type=need(_TYPE, p[5], w), basket_id=need(_ID, p[6], w), leg_id=need(_ID, p[7], w),
                                          qty=to_int(p[8], w, -MAXACTQTY, MAXACTQTY), parent_cut_id=p[9] if p[9] == '' else need(_AID, p[9], w), info_ts=to_int(p[10], w, 0, MAXT) if p[10] != '' else ts, group_id=_group(p)))
                else: raise ScenarioError(f'{w}: unknown line type {k!r}')
            except IndexError: raise ScenarioError(f'{w}: too few fields for {k}')
        if meta.get('evidence') != EVIDENCE: raise ScenarioError(f'scenario must declare META evidence {EVIDENCE} (exactly once)')
        s.name = meta.get('name', ''); s.description = meta.get('description', ''); s.method = meta.get('method', 'FIFO')
        if s.method not in ('FIFO', 'LIFO', 'AVG'): raise ScenarioError('bad method')
        for pl in s.configs:
            if pl not in seen_plugin: raise ScenarioError(f'CONFIG names plugin {pl!r} that has no PLUGIN line')
        from .risk import parse_risk
        try: parse_risk(s.risk)
        except ValueError as e: raise ScenarioError(str(e))
        for d in s.seeds + s.duplicates:
            if d['instrument_id'] not in s.instruments: raise ScenarioError(f'seed {d["fill_id"]}: undeclared instrument')
            if d['side'] not in (1, -1) or d['qty'] % s.instruments[d['instrument_id']] or d['price'] % 5: raise ScenarioError(f'seed {d["fill_id"]}: invalid side/qty/price')
            k = (d['basket_id'], d['leg_id'])
            if legdef.setdefault(k, (d['instrument_id'], d['side'])) != (d['instrument_id'], d['side']): raise ScenarioError(f'leg {k}: seeds disagree on instrument or side')
        for ts, iid, px in s.marks:
            if iid not in s.instruments or px % 5: raise ScenarioError(f'mark {iid}@{ts}: undeclared instrument or price not a multiple of the tick')
        s.seeds.sort(key=lambda d: (d['ts'], d['fill_id'])); s.duplicates.sort(key=lambda d: (d['ts'], d['fill_id'])); s.marks.sort(); s.ticks = sorted(set(s.ticks))
        s.actions.sort(key=Scenario.action_key)
        for a in s.actions:
            if a['ts'] not in s.ticks: raise ScenarioError(f'ACTION {a["action_id"]} at {a["ts"]} is not at a TICK time')
        return s

    def to_text(self):
        L = ['#PC_SCENARIO v1', f'META\tname\t{self.name}', f'META\tevidence\t{EVIDENCE}', f'META\tdescription\t{self.description}', f'META\tmethod\t{self.method}']
        L += [f'INST\t{i}\t{self.instruments[i]}' for i in sorted(self.instruments)] + [f'RISK\t{k}\t{self.risk[k]}' for k in sorted(self.risk)]
        L += [f'PLUGIN\t{n}\t{v}\t{int(e)}' for n, v, e in self.plugins]
        L += [f'CONFIG\t{p}\t{k}\t{self.configs[p][k]}' for p in sorted(self.configs) for k in sorted(self.configs[p])]
        L += [f'LEG\t{d["fill_id"]}\t{d["basket_id"]}\t{d["leg_id"]}\t{d["instrument_id"]}\t{d["side"]}\t{d["qty"]}\t{d["price"]}\t{d["ts"]}' for d in self.seeds]
        L += [f'LEG\t{d["fill_id"]}\t{d["basket_id"]}\t{d["leg_id"]}\t{d["instrument_id"]}\t{d["side"]}\t{d["qty"]}\t{d["price"]}\t{d["ts"]}' for d in sorted(self.duplicates, key=lambda d: (d['ts'], d['fill_id']))]
        L += [f'MARK\t{ts}\t{i}\t{px}' for ts, i, px in self.marks] + [f'TICK\t{t}' for t in self.ticks]
        L += [f'ACTION\t{a["ts"]}\t{a["action_id"]}\t{a["plugin"]}\t{a["version"]}\t{a["type"]}\t{a["basket_id"]}\t{a["leg_id"]}\t{a["qty"]}\t{a["parent_cut_id"]}\t{a["info_ts"]}\t{a["group_id"]}' for a in self.actions]
        return '\n'.join(L) + '\n'
