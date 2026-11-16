"""Deterministic synthetic scenario generators. Every scenario is marked SYNTHETIC_TEST_ONLY and is an illustration of the machinery, not a statement about Algo 8's real decisions."""
import random
from ._m2 import m2_schema
from .scenario import Scenario

BASE = m2_schema.days_from_civil(2026, 1, 5) * 86400 - m2_schema.IST_OFFSET_S + 9 * 3600 + 16 * 60       # 2026-01-05 09:16 IST
LOT = 65
SCE, SPE, WCE, WPE = (f'NIFTY|2026-01-08|{cp}|{k}' for cp, k in (('CE', 24000), ('PE', 24000), ('CE', 24800), ('PE', 23200)))
ENTRY = {SCE: 10000, SPE: 9000, WCE: 200, WPE: 250}
LEGS = (('SCE', SCE, -1), ('SPE', SPE, -1), ('WCE', WCE, 1), ('WPE', WPE, 1))
PLUGINS = ('basket_cut', 'basket_reentry', 'scripted_actions')


def new(name, description, cut=None, reentry=None, risk=None, enabled=PLUGINS, instruments=(SCE, SPE, WCE, WPE)):
    s = Scenario(); s.name = name; s.description = description; s.instruments = {i: LOT for i in instruments}; s.risk = dict(risk or {})
    s.plugins = [(p, '1.0.0', p in enabled) for p in PLUGINS]; s.configs = {'basket_cut': {k: str(v) for k, v in (cut or {}).items()}, 'basket_reentry': {k: str(v) for k, v in (reentry or {}).items()}}
    return s


def basket(s, bid, qty=195, ts=0, legs=LEGS, split=1, prefix=None):
    """seed fills that create a four-leg basket; `split` > 1 delivers each leg as several partial fills with slightly different prices"""
    prefix = prefix or bid
    for lid, iid, side in legs:
        part = qty // split
        for k in range(split):
            q = part if k < split - 1 else qty - part * (split - 1)
            s.seeds.append(dict(fill_id=f'{prefix}-{lid}-{k + 1}', basket_id=bid, leg_id=lid, instrument_id=iid, side=side, qty=q, price=ENTRY[iid] + 50 * k, ts=BASE + ts))


def marks(s, iid, series):
    for off, px in series: s.marks.append((BASE + off, iid, px))


def ticks(s, offs): s.ticks = sorted(set(BASE + o for o in offs))


def finish(s): s.seeds.sort(key=lambda d: (d['ts'], d['fill_id'])); s.marks.sort(); s.actions.sort(key=Scenario.action_key); return s


def flat_marks(s, upto, step=300):
    for iid in s.instruments:
        for off in range(0, upto + 1, step): s.marks.append((BASE + off, iid, ENTRY.get(iid, 10000)))


def cut_id(off, bid='B1', leg='SCE'): return f'basket_cut|{BASE + off}|{bid}|{leg}|CUT'


def s01_complete_basket():
    s = new('s01_complete_basket', 'A complete four-leg basket (short CE/PE 195, long CE/PE wings 195); the cut policy never triggers.', cut=dict(trigger_bp=2000, qty_mode='UNITS', units=65))
    basket(s, 'B1'); flat_marks(s, 900); ticks(s, [0, 300, 600, 900]); return finish(s)


def s02_partial_basket_cut():
    s = new('s02_partial_basket_cut', 'Partial basket cut: every leg is cut by one third (rounded to a lot) at a scheduled time; the re-entry cooldown has not elapsed.',
            cut=dict(policy='SCHEDULED', cut_at_ts=BASE + 300, scope='BASKET', qty_mode='FRACTION_BP', fraction_bp=3333), reentry=dict(cooldown_s=600))
    basket(s, 'B1'); flat_marks(s, 600); ticks(s, [0, 300, 600]); return finish(s)


def s03_full_basket_cut():
    s = new('s03_full_basket_cut', 'Full basket cut: every leg is cut completely (one atomic group). The re-entry plugin is registered but disabled.',
            cut=dict(policy='SCHEDULED', cut_at_ts=BASE + 300, scope='BASKET', qty_mode='FRACTION_BP', fraction_bp=10000), enabled=('basket_cut', 'scripted_actions'))
    basket(s, 'B1'); flat_marks(s, 600); ticks(s, [0, 300, 600]); return finish(s)


def s04_cut_rejected_insufficient_inventory():
    s = new('s04_cut_rejected_insufficient_inventory', 'The cut policy asks for 260 units of a 195-unit short CE leg (clamp_to_available=0); risk validation rejects it.',
            cut=dict(policy='SCHEDULED', cut_at_ts=BASE + 300, scope='LEG', leg_side_filter='SHORT', option_type_filter='CE', qty_mode='UNITS', units=260, clamp_to_available=0))
    basket(s, 'B1'); flat_marks(s, 600); ticks(s, [0, 300, 600]); return finish(s)


def _reentry_base(name, description, reentry=None, risk=None):
    s = new(name, description, cut=dict(policy='MARK_ADVERSE_MOVE', trigger_bp=2000, scope='LEG', leg_side_filter='SHORT', option_type_filter='CE', qty_mode='UNITS', units=65),
            reentry=dict(dict(cooldown_s=600, price_condition='WITHIN_BAND', band_bp=1500), **(reentry or {})), risk=dict(dict(max_gross_units=800, max_short_units=400, max_cut_qty_per_action=195, max_reentry_qty_per_action=130, reentry_min_cooldown_s=300), **(risk or {})))
    basket(s, 'B1'); flat_marks(s, 1500)
    s.marks = [m for m in s.marks if not (m[1] == SCE and m[0] - BASE in (300, 600, 900, 1200, 1500))]
    marks(s, SCE, [(300, 11000), (600, 12500), (900, 12000), (1200, 11000), (1500, 10800)]); ticks(s, [0, 300, 600, 900, 1200, 1500]); return s


def s05_reentry_success():
    return finish(_reentry_base('s05_reentry_success', 'THE EXAMPLE: short CE leg is cut by 65 after a +25% mark move at t+600s, the 600 s cooldown passes, the mark is back inside the price band, 65 units are re-entered at t+1200s.'))


def s06_reentry_rejected_cooldown():
    s = _reentry_base('s06_reentry_rejected_cooldown', 'Re-entry rejected because of cooldown: the plugin waits (cooldown 1800 s) and a scripted re-entry at t+900s is rejected by the validator (minimum cooldown 900 s).',
                      reentry=dict(cooldown_s=1800), risk=dict(reentry_min_cooldown_s=900))
    s.actions.append(dict(ts=BASE + 900, action_id='inj-early-reentry', plugin='', version='', type='REENTRY', basket_id='B1', leg_id='SCE', qty=65, parent_cut_id=cut_id(600), info_ts=BASE + 900, group_id=''))
    return finish(s)


def s07_reentry_rejected_risk_limit():
    return finish(_reentry_base('s07_reentry_rejected_risk_limit', 'Re-entry rejected by a risk limit: the short-unit limit (325) would be exceeded by restoring 65 units (390).', risk=dict(max_short_units=325)))


def s08_overlapping_baskets():
    s = new('s08_overlapping_baskets', 'Two baskets share the short CE 24000 instrument (195 + 130 units). Both are cut by 65; a scripted cut of 195 on the 130-unit basket is rejected although the ledger holds more.',
            cut=dict(policy='MARK_ADVERSE_MOVE', trigger_bp=2000, scope='LEG', leg_side_filter='SHORT', option_type_filter='CE', qty_mode='UNITS', units=65), reentry=dict(cooldown_s=900), risk=dict(max_gross_units=1200, max_short_units=700))
    basket(s, 'B1'); basket(s, 'B2', qty=130, legs=(('SCE', SCE, -1), ('WCE', WCE, 1)))
    flat_marks(s, 900); s.marks = [m for m in s.marks if not (m[1] == SCE and m[0] - BASE in (300, 600))]; marks(s, SCE, [(300, 12500), (600, 12500)]); ticks(s, [0, 300, 600, 900])
    s.actions.append(dict(ts=BASE + 600, action_id='inj-b2-overcut', plugin='', version='', type='CUT', basket_id='B2', leg_id='SCE', qty=195, parent_cut_id='', info_ts=BASE + 600, group_id=''))
    return finish(s)


def s09_partial_fills_and_duplicates():
    s = new('s09_partial_fills_and_duplicates', 'Legs are seeded by three partial fills each; one seed event is delivered twice (ignored and counted); a scripted cut id is submitted twice (second rejected as duplicate).',
            cut=dict(policy='MARK_ADVERSE_MOVE', trigger_bp=5000, qty_mode='UNITS', units=65))
    basket(s, 'B1', split=3); s.duplicates.append(dict(s.seeds[0]))
    flat_marks(s, 600); ticks(s, [0, 300, 600])
    for _ in range(2): s.actions.append(dict(ts=BASE + 300, action_id='inj-cut-1', plugin='', version='', type='CUT', basket_id='B1', leg_id='SCE', qty=65, parent_cut_id='', info_ts=BASE + 300, group_id=''))
    return finish(s)


def s10_random_stress(seed):
    r = random.Random(seed); lots = LOT; strikes = (23800, 24000, 24200); ins = [f'NIFTY|2026-01-08|{cp}|{k}' for cp in ('CE', 'PE') for k in strikes]
    cut = dict(policy=r.choice(['MARK_ADVERSE_MOVE', 'SCHEDULED']), trigger_bp=r.randint(500, 3000), cut_at_ts=BASE + 120 * r.randint(2, 10), scope=r.choice(['LEG', 'BASKET']), leg_side_filter=r.choice(['ANY', 'SHORT', 'LONG']),
               option_type_filter=r.choice(['ANY', 'CE', 'PE']), qty_mode=r.choice(['UNITS', 'FRACTION_BP']), units=lots * r.randint(1, 4), fraction_bp=r.randint(1000, 10000), clamp_to_available=r.randint(0, 1), max_cuts_per_leg=r.randint(1, 2))
    re_ = dict(cooldown_s=r.randint(0, 900), max_reentries_per_cut=r.randint(1, 2), max_reentry_fraction_bp=r.choice([5000, 10000]), qty_mode=r.choice(['RESTORE', 'UNITS']), units=lots * r.randint(1, 2), price_condition=r.choice(['NONE', 'WITHIN_BAND']), band_bp=r.randint(500, 3000))
    s = new(f's10_random_stress_seed{seed}', f'Random stress scenario, fixed seed {seed}: random baskets, random-walk marks, random configurations, random scripted (partly invalid) actions.', cut=cut, reentry=re_, instruments=tuple(ins))
    total = 0
    for b in range(3):
        legs = []; chosen = r.sample(ins, r.randint(2, 4))
        for k, iid in enumerate(chosen):
            side = r.choice([-1, 1]); q = lots * r.randint(1, 4); total += q; legs.append((f'L{k}', iid, side))
            s.seeds.append(dict(fill_id=f'b{b}-L{k}-1', basket_id=f'B{b}', leg_id=f'L{k}', instrument_id=iid, side=side, qty=q, price=5 * r.randint(1000, 4000), ts=BASE))
    s.risk = dict(max_gross_units=int(total * r.uniform(0.9, 1.3)), max_short_units=int(total * r.uniform(0.3, 0.8)), max_cut_qty_per_action=lots * r.randint(2, 6), max_reentry_qty_per_action=lots * r.randint(1, 4), reentry_min_cooldown_s=r.choice([0, 60, 300]))
    px = {i: 5 * r.randint(1000, 4000) for i in ins}; offs = list(range(0, 120 * 30 + 1, 120))
    for off in offs:
        for i in ins: px[i] = max(5, px[i] + 5 * r.randint(-60, 60)); s.marks.append((BASE + off, i, px[i]))
    s.ticks = [BASE + o for o in offs]
    known = [(sd['basket_id'], sd['leg_id']) for sd in s.seeds]
    for k in range(10):
        b, l = r.choice(known + [('B9', 'L0'), ('B0', 'ZZ')]); ts = BASE + 120 * r.randint(1, 29); typ = r.choice(['CUT', 'CUT', 'REENTRY', 'REENTRY', 'HEDGE'])
        s.actions.append(dict(ts=ts, action_id=f'inj-{k}', plugin='', version='', type=typ, basket_id=b, leg_id=l, qty=r.choice([lots, lots * 2, lots * 5, 30, 0, -65]), parent_cut_id=r.choice(['', 'nonexistent', f'basket_cut|{ts - 120}|{b}|{l}|CUT']),
                              info_ts=ts + r.choice([0, 0, 0, 60]), group_id=''))
    return finish(s)


def s11_basket_lifecycle_demo():
    """illustration used by the lifecycle plot: creation -> partial cut (plugin) -> full cut (scripted group) -> re-entry (scripted, cites the first cut)"""
    s = new('s11_basket_lifecycle_demo', 'Lifecycle illustration: ACTIVE -> partial cut of every leg by the plugin (t+300s) -> full cut of what remains (scripted group, t+900s) -> partial re-entry of the short CE leg citing the first cut (t+1500s).',
            cut=dict(policy='SCHEDULED', cut_at_ts=BASE + 300, scope='BASKET', qty_mode='FRACTION_BP', fraction_bp=3333), risk=dict(reentry_min_cooldown_s=600), enabled=('basket_cut', 'scripted_actions'))
    basket(s, 'B1'); flat_marks(s, 1500); ticks(s, [0, 300, 600, 900, 1200, 1500])
    for lid, _, _ in LEGS: s.actions.append(dict(ts=BASE + 900, action_id=f'full-cut-{lid}', plugin='', version='', type='CUT', basket_id='B1', leg_id=lid, qty=130, parent_cut_id='', info_ts=BASE + 900, group_id='full-cut'))
    s.actions.append(dict(ts=BASE + 1500, action_id='reentry-SCE', plugin='', version='', type='REENTRY', basket_id='B1', leg_id='SCE', qty=65, parent_cut_id=cut_id(300), info_ts=BASE + 1500, group_id=''))
    return finish(s)


def all_scenarios():
    out = {}
    for fn in (s01_complete_basket, s02_partial_basket_cut, s03_full_basket_cut, s04_cut_rejected_insufficient_inventory, s05_reentry_success, s06_reentry_rejected_cooldown, s07_reentry_rejected_risk_limit, s08_overlapping_baskets, s09_partial_fills_and_duplicates, s11_basket_lifecycle_demo):
        sc = fn(); out[sc.name] = sc
    for seed in (1, 7, 42):
        sc = s10_random_stress(seed); out[sc.name] = sc
    return out
