"""Clean, reproducible rebuild of every exit-engine cache and output (sections 1-10), keyed by UniqueOrderIdentifier (col 163).
1. deletes every exit-engine cache (exit_*.pkl, fp_*.pkl) so nothing built under the old col-4 order grouping survives;
   market caches (idx/opt candles, indicators) do not depend on orders and are kept;
2. runs the stages in dependency order (independent stages in parallel), logging each to results/logs/;
3. merges the per-fill replay summaries and runs the automated tests.
python3 analysis/exit_engine/run_all.py"""
import os, sys, glob, subprocess, time, json
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE); ROOT = os.path.dirname(AN)
C = os.path.join(AN, '_cache'); RES = os.path.join(HERE, 'results'); LOG = os.path.join(RES, 'logs'); os.makedirs(LOG, exist_ok=True)

def run(name, args):
    t0 = time.time(); log = os.path.join(LOG, f'{name}.txt')
    with open(log, 'w') as f: r = subprocess.run([sys.executable] + args, cwd=AN, stdout=f, stderr=subprocess.STDOUT)
    msg = f'{name}: exit {r.returncode} in {time.time() - t0:.0f}s'; print(msg, flush=True)
    if r.returncode != 0: raise SystemExit(f'STAGE FAILED: {msg} (see {log})')
    return msg

def chain(*stages):
    for n, a in stages: run(n, a)

def parallel(*chains):
    with ThreadPoolExecutor(len(chains)) as ex:
        for f in [ex.submit(chain, *c) for c in chains]: f.result()

if __name__ == '__main__':
    E = 'exit_engine/'
    resume = '--resume-models' in sys.argv          # re-run from stage 15 on the caches of this same clean build (stages 1-14 already done)
    removed = []
    if not resume:
        removed = [p for p in glob.glob(os.path.join(C, 'exit_*.pkl')) + glob.glob(os.path.join(C, 'fp_*.pkl'))]
        for p in removed: os.remove(p)
        print('removed caches:', [os.path.basename(p) for p in removed], flush=True)
    else:
        print('resume from stage 15 (no cache deletion)', flush=True)
        run('15_models', [E + 'models.py'])
    if not resume:
      chain(('01_ledger', [E + 'ledger.py']), ('02_taxonomy', [E + 'taxonomy.py']), ('03_common', [E + 'common.py']),
          ('04_order_key_audit', [E + 'order_key_audit.py']), ('05_bookstate', [E + 'bookstate.py']))
      parallel([('06_panel', [E + 'panel.py']), ('07_triggers', [E + 'triggers.py']), ('08_stop_shape', [E + 'stop_shape.py']), ('09_carry_stop', [E + 'carry_stop.py'])],
               [('10_first_passage', [E + 'first_passage.py'])],
               [('11_side_basket', [E + 'side_basket.py']), ('12_clock_b', [E + 'clock_b.py']), ('13_carried', [E + 'carried.py']), ('14_newest_ref', [E + 'newest_ref.py'])],
               [('15_models', [E + 'models.py'])])
    parallel([('16_replay_open', [E + 'replay.py', '--fill', 'open'])], [('17_replay_adverse', [E + 'replay.py', '--fill', 'adverse'])],
             [('18_replay_delay1', [E + 'replay.py', '--fill', 'delay1'])], [('19_robustness', [E + 'robustness.py'])])
    import shutil
    for n, t in [('02_taxonomy', 'taxonomy_report'), ('07_triggers', 'triggers_report'), ('08_stop_shape', 'stop_shape_report'), ('09_carry_stop', 'carry_stop_report'),
                 ('10_first_passage', 'first_passage_report'), ('11_side_basket', 'side_basket_report'), ('12_clock_b', 'clock_b_report'), ('13_carried', 'carried_report'),
                 ('14_newest_ref', 'newest_ref_report'), ('15_models', 'models_report'), ('16_replay_open', 'replay_open_report'),
                 ('17_replay_adverse', 'replay_adverse_report'), ('18_replay_delay1', 'replay_delay1_report'), ('19_robustness', 'robustness_report')]:
        shutil.copy(os.path.join(LOG, f'{n}.txt'), os.path.join(RES, f'{t}.txt'))
    import pandas as pd
    pd.concat([pd.read_csv(os.path.join(RES, f'autonomous_replay_metrics_{f}.csv')) for f in ('open', 'adverse', 'delay1')], ignore_index=True).to_csv(
        os.path.join(RES, 'autonomous_replay_metrics.csv'), index=False)
    r = subprocess.run([sys.executable, '-m', 'pytest', '-q', 'analysis/exit_engine/tests'], cwd=ROOT, capture_output=True, text=True)
    open(os.path.join(LOG, '20_tests.txt'), 'w').write(r.stdout + r.stderr); print('tests:', r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-300:])
    json.dump(dict(order_key='col 163 UniqueOrderIdentifier', finished=time.strftime('%Y-%m-%d %H:%M:%S'), removed=[os.path.basename(p) for p in removed]),
              open(os.path.join(RES, 'logs', 'build_stamp.json'), 'w'), indent=1)
