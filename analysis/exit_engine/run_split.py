"""Detached scheduler for the split exit-engine jobs (section 7 models, section 3 trigger tests).
Runs the jobs with a core budget (default 4 'thread units'), each as its own subprocess with its own log and timeout, records
results/split_status/<job>.json, then runs the merge steps.  Meant to be started detached so no single background-command
limit applies:   setsid nohup python3 analysis/exit_engine/run_split.py > <log> 2>&1 &
python3 analysis/exit_engine/run_split.py [--budget 4] [--timeout-min 150] [--only name,name] [--skip-merge]"""
import os, sys, json, time, subprocess, argparse
HERE = os.path.dirname(os.path.abspath(__file__)); AN = os.path.dirname(HERE)
RES = os.path.join(HERE, 'results'); LOG = os.path.join(RES, 'logs', 'split'); ST = os.path.join(RES, 'split_status')
os.makedirs(LOG, exist_ok=True); os.makedirs(ST, exist_ok=True)
E = 'exit_engine/'
# (name, argv, thread weight, env)  -- heaviest first
JOBS = [('m_0_multiclass', [E + 'models.py', '--only', '0_multiclass'], 2), ('m_1_lotstop', [E + 'models.py', '--only', '1_lotstop'], 2),
        ('m_1b_unsched', [E + 'models.py', '--only', '1b_unsched'], 2), ('m_5_carried', [E + 'models.py', '--only', '5_carried'], 1),
        ('m_6_salvage', [E + 'models.py', '--only', '6_salvage'], 1), ('m_6b_profit', [E + 'models.py', '--only', '6b_profit'], 1),
        ('t_t123', [E + 'triggers.py', 't123'], 1)] + \
       [(f't_t4_{i}', [E + 'triggers.py', 't4', str(i)], 1) for i in range(0, 9)] + \
       [('m_2_side', [E + 'models.py', '--only', '2_side'], 1), ('m_3_basket', [E + 'models.py', '--only', '3_basket'], 1),
        ('m_4_clockb', [E + 'models.py', '--only', '4_clockb'], 1), ('m_7_reentry', [E + 'models.py', '--only', '7_reentry'], 1), ('m_8_final', [E + 'models.py', '--only', '8_final'], 1),
        ('t_stop_shape', [E + 'stop_shape.py'], 1), ('t_carry_stop', [E + 'carry_stop.py'], 1)]
MERGES = [('merge_models', [E + 'models.py', '--merge']), ('merge_triggers', [E + 'triggers.py', 'merge'])]

def status(name, **kw):
    p = os.path.join(ST, name + '.json'); d = json.load(open(p)) if os.path.exists(p) else {}
    d.update(kw); json.dump(d, open(p, 'w'))
    return d

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--budget', type=int, default=4); ap.add_argument('--timeout-min', type=int, default=150)
    ap.add_argument('--only'); ap.add_argument('--skip-merge', action='store_true'); a = ap.parse_args()
    jobs = [j for j in JOBS if not a.only or j[0] in a.only.split(',')]
    for n, _, _ in jobs: status(n, state='pending')
    running = {}; free = a.budget; queue = list(jobs); t_start = time.time(); failed = []
    print(f'{len(jobs)} jobs, budget {a.budget}, timeout {a.timeout_min} min each', flush=True)
    while queue or running:
        # start whatever fits (heaviest first, but let lighter jobs backfill)
        for j in list(queue):
            n, argv, w = j
            if w <= free:
                env = dict(os.environ, ALGO8_THREADS=str(w), OMP_NUM_THREADS=str(w), OPENBLAS_NUM_THREADS=str(w))
                f = open(os.path.join(LOG, n + '.txt'), 'w')
                p = subprocess.Popen([sys.executable] + argv, cwd=AN, stdout=f, stderr=subprocess.STDOUT, env=env)
                running[n] = (p, w, time.time(), f); free -= w; queue.remove(j); status(n, state='running', start=time.strftime('%H:%M:%S'))
                print(f'[{time.strftime("%H:%M:%S")}] start {n} (w={w})', flush=True)
        time.sleep(5)
        for n, (p, w, t0, f) in list(running.items()):
            rc = p.poll(); to = (time.time() - t0) > a.timeout_min * 60
            if rc is None and not to: continue
            if rc is None: p.kill(); rc = -9
            f.close(); free += w; del running[n]
            state = 'done' if rc == 0 else ('timeout' if rc == -9 else 'failed')
            status(n, state=state, rc=rc, minutes=round((time.time() - t0) / 60, 1), end=time.strftime('%H:%M:%S'))
            if rc != 0: failed.append(n)
            print(f'[{time.strftime("%H:%M:%S")}] {state} {n} in {(time.time() - t0) / 60:.1f} min (rc={rc})', flush=True)
    if not a.skip_merge:
        for n, argv in MERGES:
            f = open(os.path.join(LOG, n + '.txt'), 'w'); rc = subprocess.run([sys.executable] + argv, cwd=AN, stdout=f, stderr=subprocess.STDOUT).returncode; f.close()
            status(n, state='done' if rc == 0 else 'failed', rc=rc); print(f'[{time.strftime("%H:%M:%S")}] {n}: rc={rc}', flush=True)
    print(f'ALL FINISHED in {(time.time() - t_start) / 60:.1f} min; failed/timeout: {failed or "none"}', flush=True)
