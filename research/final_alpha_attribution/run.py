"""Recreate the finite final economic investigation; no remote market calls."""
import os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
    env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';env.setdefault('MPLCONFIGDIR',str(HERE/'.cache/matplotlib'));env.setdefault('XDG_CACHE_HOME',str(HERE/'.cache'))
    for script in ['audit.py','economics.py','benchmarks.py','attribution.py','summarize.py','report.py','validate.py']:
        print('Running',script,flush=True);subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,env=env,check=True)
    print('Research closed. No subsequent search is launched.',flush=True)
if __name__=='__main__':main()
