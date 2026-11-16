"""Scenario file (tab separated, '#' comment lines). Every scenario must declare META evidence SYNTHETIC_TEST_ONLY.

META  key value                 INST  instrument_id lot_size           RISK  key value
PLUGIN name version enabled     (registration = evaluation order)      CONFIG plugin key value
LEG   fill_id basket leg instrument side qty price_paise ts            (the seed fills that create a basket)
MARK  ts instrument price_paise TICK  ts                                (ticks = times at which plugins are evaluated)
ACTION ts action_id plugin version type basket leg qty parent_cut_id info_ts group_id   (offered to the scripted_actions plugin at exactly `ts`)
Canonical order inside the file never changes a result: LEG/MARK/TICK/ACTION lines are sorted after loading."""
from . import EVIDENCE


class ScenarioError(Exception): pass


def _i(x, what):
    try: return int(x)
    except ValueError: raise ScenarioError(f'{what}: not an integer: {x!r}')


class Scenario:
    def __init__(self):
        self.name = ''; self.description = ''; self.method = 'FIFO'; self.instruments = {}; self.risk = {}; self.plugins = []; self.configs = {}
        self.seeds = []; self.marks = []; self.ticks = []; self.actions = []; self.duplicates = []          # duplicates: identical repeated LEG events (ignored, counted)

    @staticmethod
    def action_key(a): return (a['ts'], a['action_id'], a['plugin'], a['version'], a['type'], a['basket_id'], a['leg_id'], a['qty'], a['parent_cut_id'], a['info_ts'], a['group_id'])

    @property
    def duplicate_seeds(self): return len(self.duplicates)

    @staticmethod
    def load(path): return Scenario.parse(open(path, encoding='utf-8').read())

    @staticmethod
    def parse(text):
        s = Scenario(); meta = {}; seen_fill = {}; legdef = {}; markpx = {}
        for n, line in enumerate(text.split('\n'), 1):
            if not line.strip() or line.startswith('#'): continue
            p = line.split('\t'); k = p[0]; w = f'line {n}'
            try:
                if k == 'META': meta[p[1]] = p[2] if len(p) > 2 else ''
                elif k == 'INST': s.instruments[p[1]] = _i(p[2], w)
                elif k == 'RISK': s.risk[p[1]] = _i(p[2], w)
                elif k == 'PLUGIN': s.plugins.append((p[1], p[2], p[3] == '1'))
                elif k == 'CONFIG': s.configs.setdefault(p[1], {})[p[2]] = p[3]
                elif k == 'LEG':
                    d = dict(fill_id=p[1], basket_id=p[2], leg_id=p[3], instrument_id=p[4], side=_i(p[5], w), qty=_i(p[6], w), price=_i(p[7], w), ts=_i(p[8], w))
                    if d['fill_id'] in seen_fill:
                        if seen_fill[d['fill_id']] != d: raise ScenarioError(f'{w}: fill_id {d["fill_id"]} repeated with different content')
                        s.duplicates.append(d); continue                       # an identical repeat is a duplicate event: ignored and counted
                    seen_fill[d['fill_id']] = d; s.seeds.append(d)
                elif k == 'MARK':
                    key = (_i(p[1], w), p[2]); px = _i(p[3], w)
                    if key in markpx and markpx[key] != px: raise ScenarioError(f'{w}: conflicting marks for {key}')
                    if key not in markpx: markpx[key] = px; s.marks.append((key[0], key[1], px))
                elif k == 'TICK': s.ticks.append(_i(p[1], w))
                elif k == 'ACTION':
                    s.actions.append(dict(ts=_i(p[1], w), action_id=p[2], plugin=p[3], version=p[4], type=p[5], basket_id=p[6], leg_id=p[7], qty=_i(p[8], w), parent_cut_id=p[9], info_ts=_i(p[10], w) if p[10] != '' else _i(p[1], w), group_id=p[11] if len(p) > 11 else ''))
                else: raise ScenarioError(f'{w}: unknown line type {k!r}')
            except IndexError: raise ScenarioError(f'{w}: too few fields for {k}')
        if meta.get('evidence') != EVIDENCE: raise ScenarioError(f'scenario must declare META evidence {EVIDENCE}')
        s.name = meta.get('name', ''); s.description = meta.get('description', ''); s.method = meta.get('method', 'FIFO')
        if s.method not in ('FIFO', 'LIFO', 'AVG'): raise ScenarioError('bad method')
        for d in s.seeds:
            if d['instrument_id'] not in s.instruments: raise ScenarioError(f'seed {d["fill_id"]}: undeclared instrument')
            if d['side'] not in (1, -1) or d['qty'] <= 0 or d['qty'] % s.instruments[d['instrument_id']] or d['price'] <= 0 or d['price'] % 5: raise ScenarioError(f'seed {d["fill_id"]}: invalid side/qty/price')
            k = (d['basket_id'], d['leg_id'])
            if legdef.setdefault(k, (d['instrument_id'], d['side'])) != (d['instrument_id'], d['side']): raise ScenarioError(f'leg {k}: seeds disagree on instrument or side')
        for ts, iid, px in s.marks:
            if iid not in s.instruments or px <= 0 or px % 5: raise ScenarioError(f'mark {iid}@{ts}: undeclared instrument or invalid price')
        s.seeds.sort(key=lambda d: (d['ts'], d['fill_id'])); s.duplicates.sort(key=lambda d: (d['ts'], d['fill_id'])); s.marks.sort(); s.ticks = sorted(set(s.ticks))
        s.actions.sort(key=Scenario.action_key)
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
