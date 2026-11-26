"""Freeze the D0 parameters for the 3-year backtest (plan reports/BACKTEST3Y_PLAN.md): the same fit as bl_d0_fr.py with training = ALL 30 live cycles with both logs.
Writes outputs/bl_bt3_frozen.json (params, code commit, data commit) and outputs/bl_bt3_frozen_waves.csv (timetable waves per underlying x version). Run BEFORE any run on another cycle."""
import sys, json, subprocess, warnings; sys.path.insert(0, '.'); warnings.filterwarnings('ignore')
from bl_common import *
import bl_d0_fr as F
P = F.fit(F.D0C, F.D0C, {'V1': 'V1', 'V2': 'V2'}); W = P['W']
commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, cwd='/home/user/Algo-8-Reverse-Engineer').stdout.strip()
J = dict(code_commit_before_freeze=commit, data_commit='eb4097308d47ccc75078ab73ba76d33bb1c7030b', trained_on_cycles=len(F.D0C), k3=P['k3'], m1=list(P['m1']), counter_r=P['r'], opening_longs=P['ow'], waves=int(len(W)), cycle_stop_rs=float(F.L_STOP),
         waves_by_group={f'{a}|{b}': int(n) for (a, b), n in W.groupby(['und', 'version']).size().items()})
json.dump(J, open(f'{OUT}/bl_bt3_frozen.json', 'w'), indent=1, default=str); W.to_csv(f'{OUT}/bl_bt3_frozen_waves.csv', index=False); print(json.dumps(J, indent=1, default=str)); print(W.head(3).to_string())
