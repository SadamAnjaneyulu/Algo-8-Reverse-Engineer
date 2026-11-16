#!/bin/bash
# Track E: run my own independent detectors against mutant mirrors (read-only on the mirrors; outputs only under $S/own). usage: own_checks.sh <S scratch> <track scripts dir>
S=$1; T=$2; mkdir -p $S/own; cd $S
# E07: provenance sha vs real HEAD of a clone
python3 - <<PY > $S/own/E07.txt 2>&1
import sys,subprocess; sys.path.insert(0,'$S/mut/E07/portfolio_engine/python'); from pe import provenance
print('git_sha under mutant:', provenance.git_sha('$S/det/g1'), 'real HEAD:', subprocess.check_output(['git','-C','$S/det/g1','rev-parse','HEAD']).decode().strip())
PY
# E08: parse probe (schema_version variant)
python3 $T/parse_probe.py --root $S/mut/E08 --work $S/own/E08 2>&1 | grep -E "bad_schema_version|baseline" > $S/own/E08.txt
# E09/E16: cross-midnight parity vs unmodified C++ (own fuzz, small)
for id in E09 E16 E03 E04 E12 E19; do [ -d $S/mut/$id ] && python3 $T/parity_fuzz.py --root $S/mut/$id --work $S/own/$id --n 21 2>&1 | head -2 > $S/own/$id.txt; done
# E11: nondeterminism across PYTHONHASHSEED (batch files hash)
for seed in 1 2 3; do PYTHONHASHSEED=$seed python3 - <<PY >> $S/own/E11.txt 2>&1
import sys,hashlib; sys.path.insert(0,'$S/mut/E11/portfolio_engine/python'); from pe import tsvio, closing_batches as cb
from pe.lineage_set import LineageSet
ins=tsvio.read_instruments('$S/base/portfolio_engine/data_generated/historical_instruments.tsv'); f=tsvio.read_events('$S/base/portfolio_engine/data_generated/historical_events.tsv',ins)
ls=LineageSet(f[:8000],ins,'HISTORICAL_OBSERVED_REPLAY','src'); p,u,m=cb.closing_parents(ls); V=cb.all_views(p)
print($seed, hashlib.sha256(cb.files_for_method(V,'C1',ls)['closing_batches_C1.tsv'].encode()).hexdigest()[:12])
PY
done
# E15/E02/E01: id audit
for id in E15 E02; do python3 $T/id_audit.py $S/mut/$id $S/own/id_$id.json 2>&1 | grep -E "fill_id_is_F|lifecycle_event_id_dupes|oa_cp_id" | head -3 > $S/own/$id.txt; done
