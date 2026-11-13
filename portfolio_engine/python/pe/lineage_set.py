"""LineageSet: the three conventions replayed on the same events, observed layer asserted identical across them (the separation guard), plus queries and the M2-B invariants.
Observed = what the fills prove. Analytical = what a convention attributes. The query results keep the two apart and say so."""
from collections import defaultdict
from .schema import *
from . import replay as rp, lineage as ln
from .parents import parent_roles


class LineageSet:
    def __init__(self, fills, instruments, mode, tie_order='src', parents=None):
        self.mode = mode; self.tie = tie_order; self.instruments = instruments; self.parents_meta = parents or {}; self.runs = {}; self.files = {}
        for m in METHODS:
            r = rp.replay(fills, instruments, mode, m, tie_order, lineage=True); self.runs[m] = r; self.files[m] = rp.lineage_files(r)
        ref = self.files['FIFO']
        for m in ('LIFO', 'AVG'):                       # THE separation guard: switching convention must not change any observed-layer byte
            for name in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv'):
                if self.files[m][name] != ref[name]: raise InvariantViolation(f'observed layer {name} differs between FIFO and {m}: convention leaked into the observed layer')
        rec = self.runs['FIFO'].lineage; self.oa = {r[1]: r for r in rec.observed if r[0] == 'OA'}; self.cp = {r[1]: r for r in rec.observed if r[0] == 'CP'}
        self.events = rec.events; self.episodes = self.runs['FIFO'].state.episodes; self.roles = parent_roles(rec.observed)
        self.ca = {m: self.runs[m].lineage.ca for m in METHODS}
        self._by_ep_events = defaultdict(list)
        for e in self.events: self._by_ep_events[e[1]].append(e)
        self.sensitivity = self._cp_sensitivity()

    # ---------------------------------------------------------------- analytical sensitivity: do FIFO and LIFO attribute a closing portion to different opening allocations?
    def _cp_sensitivity(self):
        f = defaultdict(dict); l = defaultdict(dict)
        for r in self.ca['FIFO']: f[r[2]][r[3]] = f[r[2]].get(r[3], 0) + r[4]
        for r in self.ca['LIFO']: l[r[2]][r[3]] = l[r[2]].get(r[3], 0) + r[4]
        return {cp: ('NONE' if f[cp] == l[cp] else 'CONVENTION_SENSITIVE') for cp in self.cp}

    # ---------------------------------------------------------------- queries
    def episode_view(self, episode_id, convention='FIFO'):
        ep = self.episodes[episode_id]; oas = [self.oa[k] for k in self.oa if self.oa[k][5] == episode_id]; cps = [self.cp[k] for k in self.cp if self.cp[k][5] == episode_id]
        cas = [r for r in self.ca[convention] if r[2] in {c[1] for c in cps}]; rem = self._slices(convention, episode_id)
        parents = sorted({r[3] for r in oas + cps})
        return dict(episode_id=episode_id,
                    observed=dict(layer='OBSERVED (identical under FIFO, LIFO and AVG)', instrument_id=ep['instrument_id'], direction=ep['direction'], started_by_reversal=ep['started_by_reversal'], opened=ep['opened'], closed=ep['closed'], remaining=ep['opened'] - ep['closed'],
                                  ended_by=ep['ended_by'], terminal_status=ln.terminal_status(self.runs['FIFO'].state, ep, self.instruments, self.runs['FIFO'].last_day), opening_allocations=oas, closing_portions=cps, lifecycle=list(self._by_ep_events[episode_id]),
                                  parents=[dict(parent_order_id=p, role=self.roles[p], metadata=self.parents_meta.get(p)) for p in parents]),
                    analytical=dict(layer=f'ANALYTICAL ({convention}; a convention, not a recorded fact)', convention=convention, closing_allocations=cas, remaining_slices=rem,
                                    ownership_claim='NONE: average-cost pool, no individual opening-source ownership' if convention == 'AVG' else 'CONVENTION-DEPENDENT attribution; FIFO and LIFO may differ',
                                    cp_sensitivity={c[1]: self.sensitivity[c[1]] for c in cps}))

    def _slices(self, convention, episode_id):
        r = self.runs[convention]; text = ln.slices_tsv(r.state, r.lineage).splitlines()[1:]; return [t.split('\t') for t in text if t.split('\t')[4] == episode_id]

    def trace_forward(self, oa_id, convention='FIFO'):
        """opening fill -> episode -> OA -> closing allocations -> closing portions -> remaining quantity"""
        oa = self.oa[oa_id]; cas = [r for r in self.ca[convention] if r[3] == oa_id]
        if convention == 'AVG': cas = [r for r in self.ca['AVG'] if r[3] == f'POOL:{oa[5]}']; own = 'NOT_IDENTIFIABLE'
        else: own = 'IDENTIFIED_BY_CONVENTION'
        used = sum(r[4] for r in cas) if convention != 'AVG' else None
        return dict(oa=oa, convention=convention, ownership=own, closing_allocations=cas, allocated_qty=used, remaining_qty=(oa[8] - used) if used is not None else None)

    def trace_backward(self, cp_id, convention='FIFO'):
        cp = self.cp[cp_id]; cas = [r for r in self.ca[convention] if r[2] == cp_id]; return dict(cp=cp, convention=convention, allocations=cas, sources=[r[3] for r in cas], sensitivity=self.sensitivity[cp_id])

    def parent_view(self, parent_id):
        oas = [r for r in self.oa.values() if r[3] == parent_id]; cps = [r for r in self.cp.values() if r[3] == parent_id]
        return dict(parent_order_id=parent_id, role=self.roles[parent_id], opening_allocations=oas, closing_portions=cps, opened_units=sum(r[8] for r in oas), closed_units=sum(r[8] for r in cps), metadata=self.parents_meta.get(parent_id))

    def mixed_parents(self): return sorted(p for p, r in self.roles.items() if r == 'MIXED')

    # ---------------------------------------------------------------- invariants (independent re-derivation from the emitted tables)
    def check(self, fills=None):
        """I1-I7, I10, I11 of docs/POSITION_LINEAGE_RULES.md; raises InvariantViolation with the first failure; returns the list of invariant ids that passed"""
        passed = []
        def ok(i, cond, msg=''):
            if not cond: raise InvariantViolation(f'{i}: {msg}')
            if i not in passed: passed.append(i)
        st = self.runs['FIFO'].state
        oa_by_inst = defaultdict(int); cp_by_inst = defaultdict(int); oa_by_ep = defaultdict(int); cp_by_ep = defaultdict(int); per_fill = defaultdict(lambda: [0, 0, 0, 0])
        for r in self.oa.values(): oa_by_inst[r[4]] += r[8]; oa_by_ep[r[5]] += r[8]; per_fill[r[2]][0] += 1; per_fill[r[2]][2] += r[8]
        for r in self.cp.values(): cp_by_inst[r[4]] += r[8]; cp_by_ep[r[5]] += r[8]; per_fill[r[2]][1] += 1; per_fill[r[2]][3] += r[8]
        for iid in st.s: ok('I1', oa_by_inst[iid] - cp_by_inst[iid] == abs(st.signed_inventory(iid)), iid)
        for eid, e in self.episodes.items(): ok('I2', oa_by_ep[eid] - cp_by_ep[eid] == e['opened'] - e['closed'], eid)
        for m in METHODS:
            ca = self.ca[m]; cp_alloc = defaultdict(int)
            for r in ca: cp_alloc[r[2]] += r[4]
            for cp_id, r in self.cp.items(): ok('I4', cp_alloc[cp_id] == r[8], f'{m} {cp_id}')
            if m != 'AVG':
                alloc = defaultdict(int)
                for r in ca: alloc[r[3]] += r[4]
                rem = {x[3]: int(x[5]) for x in (t.split('\t') for t in ln.slices_tsv(self.runs[m].state, self.runs[m].lineage).splitlines()[1:])}
                for oa_id, r in self.oa.items(): ok('I3', r[8] == alloc[oa_id] + rem.get(oa_id, 0), f'{m} {oa_id}')
                ok('I7', sum(rem.values()) == st.opened - st.closed, f'{m} remaining slices {sum(rem.values())}')
            else:
                pool = defaultdict(int)
                for r in ca: pool[r[3]] += r[4]
                pool_rem = {x[3]: int(x[5]) for x in (t.split('\t') for t in ln.slices_tsv(self.runs['AVG'].state, self.runs['AVG'].lineage).splitlines()[1:])}
                for eid in self.episodes: ok('I3', oa_by_ep[eid] == pool[f'POOL:{eid}'] + pool_rem.get(f'POOL:{eid}', 0), f'AVG pool {eid}')
                ok('I7', sum(pool_rem.values()) == st.opened - st.closed)
                ok('I-AVG-no-ownership', all(r[9] == 'NOT_IDENTIFIABLE' and r[3].startswith('POOL:') for r in ca))
            tot = sum(r[7] for r in ca) if m == 'AVG' else sum(int(r[7]) for r in ca)
            m1 = self.runs[m].state.realized_total(); ok('I6', abs(tot - m1) <= 1e-6 * max(1, len(ca)) if m == 'AVG' else tot == m1, f'{m} {tot} vs {m1}')
        for fid, (n_oa, n_cp, q_oa, q_cp) in per_fill.items():
            ok('I5', n_oa <= 1 and n_cp <= 1, fid)
        if fills is not None:
            q = {f.fill_id: f.quantity for f in fills if not f.is_duplicate_fill}
            for fid, qq in q.items(): ok('I5', per_fill[fid][2] + per_fill[fid][3] == qq, f'{fid} {per_fill[fid]} vs {qq}')
        for fid, (n_oa, n_cp, _, _) in per_fill.items():
            if n_oa and n_cp:
                oa = self.oa[f'OA:{fid}']; cp = self.cp[f'CP:{fid}']
                ok('I11', oa[5] != cp[5] and self.episodes[cp[5]]['ended_by'] == 'reversal' and self.episodes[oa[5]]['started_by_reversal'], fid)
        # I10: an EXPIRED_UNCLOSED episode keeps its remaining units as slices and receives no settlement P&L: its realized P&L is exactly the sum of its closing allocations
        last = self.runs['FIFO'].last_day
        for m in METHODS:
            cp_ep = {c: r[5] for c, r in self.cp.items()}; ca_pnl = defaultdict(float)
            for r in self.ca[m]: ca_pnl[cp_ep[r[2]]] += float(r[7])
            slices_ep = defaultdict(int)
            for t in ln.slices_tsv(self.runs[m].state, self.runs[m].lineage).splitlines()[1:]: x = t.split('\t'); slices_ep[x[4]] += int(x[5])
            for eid, e in self.runs[m].state.episodes.items():
                if ln.terminal_status(self.runs[m].state, e, self.instruments, last) == 'EXPIRED_UNCLOSED':
                    ok('I10', abs(float(e['realized']) - ca_pnl[eid]) <= 1e-6 and slices_ep[eid] == e['opened'] - e['closed'], f'{m} {eid}')
        ok('I10', True)
        ok('I-observed-layer-identical-across-conventions', all(self.files[m][n] == self.files['FIFO'][n] for m in ('LIFO', 'AVG') for n in ('observed_allocations.tsv', 'lifecycle.tsv', 'episodes.tsv')))
        return passed
