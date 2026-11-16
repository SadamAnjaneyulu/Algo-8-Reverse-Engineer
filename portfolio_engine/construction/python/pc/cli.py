"""python -m pc.cli run <scenario.scn> --out <dir>      run one scenario and write the seven output files
python -m pc.cli generate <dir>                        write every generator scenario (.scn) to <dir>"""
import argparse, os, sys
from .scenario import Scenario
from .engine import Simulation


def main(argv=None):
    ap = argparse.ArgumentParser(prog='pc.cli'); sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run'); r.add_argument('scenario'); r.add_argument('--out', required=True)
    g = sub.add_parser('generate'); g.add_argument('dir')
    a = ap.parse_args(argv)
    if a.cmd == 'run':
        Simulation(Scenario.load(a.scenario)).write(a.out); print('wrote', a.out)
    else:
        from . import generators
        os.makedirs(a.dir, exist_ok=True)
        for name, sc in generators.all_scenarios().items():
            with open(os.path.join(a.dir, name + '.scn'), 'w', encoding='utf-8', newline='\n') as f: f.write(sc.to_text())
        print('wrote', len(generators.all_scenarios()), 'scenarios to', a.dir)


if __name__ == '__main__': main()
