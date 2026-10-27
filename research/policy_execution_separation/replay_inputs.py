"""Read existing evidence; regenerate disposable inputs without writing old outputs."""
import importlib.util,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PRIOR=ROOT/'research/hypothesis_controller_search'


def market_cache(force_local=False):
    original=PRIOR/'.cache'
    if not force_local and (original/'replay.bin').exists() and (original/'cycle_34.npz').exists():return original
    target=HERE/'.cache/market_cache'
    if not (target/'replay.bin').exists() or not (target/'cycle_34.npz').exists():
        spec=importlib.util.spec_from_file_location('algo8_canonical_cache_adapter',PRIOR/'prepare.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.OUT=HERE/'.cache/cache_build_evidence';module.CACHE=target
        module.OUT.mkdir(parents=True,exist_ok=True);target.mkdir(parents=True,exist_ok=True)
        module.build()
    return target


def calibration_path():
    c=json.loads((PRIOR/'outputs/calibration.json').read_text())
    values=np.array(c['index_clock']).ravel().tolist()+np.array(c['pooled_clock']).ravel().tolist()
    for row in c['caps']:values.extend(row[k] for k in ['side_units','vega_rupees','iv_pct'])
    path=HERE/'.cache/calibration.txt';path.parent.mkdir(exist_ok=True);path.write_text(' '.join(map(str,values)))
    return path
