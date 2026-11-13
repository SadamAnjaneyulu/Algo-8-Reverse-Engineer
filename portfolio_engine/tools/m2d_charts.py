"""M2-D charts from the committed M2-D link files (HISTORICAL_OBSERVED_REPLAY); each PNG has its data CSV beside it. python3 portfolio_engine/tools/m2d_charts.py -> reports/m2d_figures/"""
import gzip, io, json, os
HERE = os.path.dirname(os.path.abspath(__file__)); PE = os.path.dirname(HERE); D = os.path.join(PE, 'reports', 'm2d_data'); OUT = os.path.join(PE, 'reports', 'm2d_figures'); os.makedirs(OUT, exist_ok=True)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt, numpy as np, pandas as pd
rd = lambda n: pd.read_csv(io.StringIO(gzip.open(os.path.join(D, n), 'rt').read()), sep='\t'); S = json.load(open(os.path.join(D, 'm2d_summary.json')))
W1 = rd('wing_body_links_W1.tsv.gz'); W60 = rd('wing_body_links_W1_S60.tsv.gz'); items = rd('wing_body_items.tsv.gz')
STAMP = 'Source: Trades_GKOHNP140.csv (sha256 86e65ab6…) → TP-01 ledger; mode HISTORICAL_OBSERVED_REPLAY. Wing = long `h_` item, body = short `num` item (module tags = attribution only). All links are INFERRED candidates; a link is not ownership and not evidence of protective intent. Units: units, seconds, strike points.'
op1 = W1[W1.level == 'OPENING']; op60 = W60[W60.level == 'OPENING']
# 1 candidates per wing
c1 = op1.groupby('wing_item').size().clip(upper=12); c60 = op60.groupby('wing_item').size().clip(upper=12); wi = items[(items.level == 'OPENING') & (items.role == 'WING')]
cnt = pd.DataFrame({'candidates': range(0, 13)}); cnt['W1_wings'] = [(len(wi) - len(c1)) if k == 0 else int((c1 == k).sum()) for k in cnt.candidates]; cnt['W1_S60_wings'] = [(len(wi) - len(c60)) if k == 0 else int((c60 == k).sum()) for k in cnt.candidates]; cnt.to_csv(os.path.join(OUT, 'm2d_candidates_per_wing.csv'), index=False)
fig, ax = plt.subplots(1, 3, figsize=(17, 4.3)); x = np.arange(13); ax[0].bar(x - 0.2, cnt.W1_wings, 0.4, label='W1 (same entry minute)'); ax[0].bar(x + 0.2, cnt.W1_S60_wings, 0.4, label='W1_S60 (±60 s)'); ax[0].set_xticks(x); ax[0].set_xticklabels([str(k) if k < 12 else '12+' for k in cnt.candidates]); ax[0].set_title('Opening wings by number of candidate bodies (0 = unmatched)', fontsize=9); ax[0].legend(fontsize=7); ax[0].set_xlabel('candidate bodies')
# 2 dt
dt = op1.dt_s.clip(-120, 120); h, e = np.histogram(dt, bins=np.arange(-120, 121, 4)); pd.DataFrame({'bin_left_s': e[:-1], 'W1_links': h}).to_csv(os.path.join(OUT, 'm2d_dt_hist_W1.csv'), index=False); ax[1].bar(e[:-1], h, width=4, align='edge'); ax[1].set_title('W1 links: wing first fill − body first fill (s; clipped ±120)', fontsize=9); ax[1].set_xlabel('seconds (negative = wing executed first)')
# 3 group ratio
g = op1.groupby(['underlying', 'expiry', 'right', 'session', 'wing_item']).size()
gr = items[(items.level == 'OPENING') & (items.entry_minute_s != 'NA')].copy(); gr['grp'] = gr.underlying + gr.expiry + gr.right + gr.entry_minute_s.astype(str); P = gr.pivot_table(index='grp', columns='role', values='qty', aggfunc='sum').dropna(); r = (P.WING / P.BODY).clip(upper=4); h2, e2 = np.histogram(r, bins=np.arange(0, 4.05, 0.1)); pd.DataFrame({'bin_left': e2[:-1], 'groups': h2}).to_csv(os.path.join(OUT, 'm2d_group_ratio_hist.csv'), index=False)
ax[2].bar(e2[:-1], h2, width=0.1, align='edge'); ax[2].set_yscale('log'); ax[2].set_title(f'Observed wing/body unit ratio per group ({len(P)} groups; exactly 1:1 in {(P.WING == P.BODY).mean():.1%} of these groups with both sides; 7,958 groups in total)', fontsize=8); ax[2].set_xlabel('wing units / body units (clipped at 4)')
fig.text(0.01, 0.005, STAMP, fontsize=6, wrap=True, va='bottom'); plt.tight_layout(rect=(0, 0.07, 1, 1)); plt.savefig(os.path.join(OUT, 'm2d_overview.png'), dpi=130); plt.close()
print(sorted(os.listdir(OUT)))
