"""Task B: what does the exceptional row 8079 (epoch 56.6 s before its id time) do to timestamp-dependent outputs if the id time were right? (hypothetical; NOT a recommendation) [RAW]+[IMPL]"""
import json, collections
import rv_replay as R
import a_batches as AB   # reuses reviewer batch rule; prints its own summary on import
F = AB.F
base_u = AB.units('source_row'); G = (2, 5, 10, 30, 60)
B = {g: AB.batches(base_u, g) for g in G}
orig = F[8079]['ep']; F[8079]['ep'] = 1782986310           # = round-half-up(id ns)
u2 = AB.units('source_row'); res = {'row8079_epoch_original': orig, 'row8079_epoch_if_id_time': 1782986310, 'closing_split_8079': R.replay(F, 'source_row')['split'][8079]}
res['batches_not_in_alternative'] = {g: len(B[g] - AB.batches(u2, g)) for g in G}
F[8079]['ep'] = orig
json.dump(res, open('b_row8079_effect_result.json', 'w'), indent=1); print(res)
