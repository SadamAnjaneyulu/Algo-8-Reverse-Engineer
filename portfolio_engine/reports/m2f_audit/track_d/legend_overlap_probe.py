"""[INV]/visual probe: for every figure drawn by tools/m2e_charts.py (run on a SCRATCH COPY), count data points / bar & line extents hidden under any axes legend.
Usage: python3 legend_overlap_probe.py <scratch PE root>.  Monkeypatches Fig.finish; writes nothing but PNG/CSV into the SCRATCH copy."""
import sys, os, json
PE = sys.argv[1]; sys.path.insert(0, os.path.join(PE, 'tools')); sys.path.insert(0, os.path.join(PE, 'python'))
import matplotlib; matplotlib.use('Agg')
import numpy as np, m2e_charts as CH
from matplotlib.collections import PathCollection, LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
res = []
orig = CH.Fig.finish
def finish(self, *a, **k):
    self.fig.canvas.draw(); r = self.fig.canvas.get_renderer()
    for ax in self.fig.axes:
        lg = ax.get_legend()
        if lg is None: continue
        bb = lg.get_window_extent(r); hid = 0; kinds = []
        for c in ax.collections:
            if isinstance(c, PathCollection):
                off = c.get_offsets()
                if len(off):
                    try: pts = ax.transData.transform(np.asarray(off, dtype=float)); 
                    except Exception: pts = np.empty((0, 2))
                    hid += int(sum(bb.contains(x, y) for x, y in pts))
            if isinstance(c, LineCollection):                      # hlines
                for seg in c.get_segments():
                    pts = ax.transData.transform(np.asarray(seg, dtype=float)); hid += int(any(bb.contains(x, y) for x, y in pts))
        for p in ax.patches:
            if isinstance(p, Rectangle) and p.get_width() and p.get_height():
                e = p.get_window_extent(r); 
                if e.width > 0 and e.height > 0 and bb.overlaps(e) and p.get_facecolor()[3] > 0.05: hid += 1; kinds.append('bar')
        for ln in ax.lines:
            if len(ln.get_xdata()) > 1 or ln.get_marker() not in ('None', None, ''):
                try: pts = ax.transData.transform(np.column_stack([matplotlib.dates.date2num(ln.get_xdata()) if hasattr(ln.get_xdata()[0], 'year') else ln.get_xdata(), ln.get_ydata()]).astype(float)); hid += int(sum(bb.contains(x, y) for x, y in pts))
                except Exception: pass
        res.append(dict(figure=self.vid, cycle=self.cycle, hidden_under_legend=hid, bar_overlaps=len(kinds)))
    return orig(self, *a, **k)
CH.Fig.finish = finish
for cy in ('NIFTY_2026-06-30', 'SENSEX_2026-07-16'): CH.build_all(cy)
for r in res:
    if r['hidden_under_legend']: print(r)
print('legend probes:', len(res))
