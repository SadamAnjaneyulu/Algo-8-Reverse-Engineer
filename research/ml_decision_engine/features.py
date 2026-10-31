"""Causal market features and training-only regime boundaries."""
from __future__ import annotations
import numpy as np
import pandas as pd

WINDOWS = (1, 3, 5, 15, 30)


def market_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Input bars are START stamped. Output is available one minute later.

    Process one underlying/session at a time. Reindexing is mandatory: missing
    minutes remain NaN and cannot masquerade as a shorter lookback. Cash-index
    volume is often unavailable: report missing VWAP, not an invented proxy.
    """
    b = bars.sort_index().copy()
    if b.index.has_duplicates:
        raise ValueError('Duplicate market bar timestamps')
    b = b.reindex(pd.date_range(b.index.min(), b.index.max(), freq='min'))
    c, h, lo = b.close, b.high, b.low
    r = np.log(c.where(c.gt(0))).diff()
    tr = pd.concat([h-lo, (h-c.shift()).abs(), (lo-c.shift()).abs()], axis=1).max(axis=1)
    tr[b[['high', 'low', 'close']].isna().any(axis=1)] = np.nan
    out = pd.DataFrame(index=b.index)
    out['spot'] = c
    out['opening_gap_pct'] = np.nan  # attached using previous received session below
    out['opening_range_pct'] = 100*(b.high.iloc[0]-b.low.iloc[0])/b.open.iloc[0]
    out['intraday_high_distance_pct'] = 100*(c/h.cummax()-1)
    out['intraday_low_distance_pct'] = 100*(c/lo.cummin()-1)
    vol = b.get('volume', pd.Series(np.nan, index=b.index)).where(lambda x: x.gt(0))
    typical = (h+lo+c)/3
    vwap = (typical*vol).cumsum()/vol.cumsum()
    out['vwap_distance_pct'] = 100*(c/vwap-1)
    for w in WINDOWS:
        n = max(w, 2)
        complete=c.notna().rolling(w+1,min_periods=w+1).sum().eq(w+1)
        out[f'return_{w}'] = (100*(c/c.shift(w)-1)).where(complete)
        out[f'atr_{w}'] = tr.rolling(w, min_periods=w).mean()
        out[f'atr_pct_{w}'] = 100*out[f'atr_{w}']/c
        out[f'rv_{w}'] = r.rolling(n, min_periods=n).std()*100*np.sqrt(n)
        out[f'range_{w}'] = 100*(h.rolling(w).max()-lo.rolling(w).min())/c
        out[f'efficiency_{w}'] = (c-c.shift(w)).abs()/c.diff().abs().rolling(w).sum().replace(0, np.nan)
        # Median increment is robust to an isolated outlying close.
        out[f'slope_{w}'] = 100*c.diff().rolling(w).median()/c
        out[f'persistence_{w}'] = np.sign(c.diff()).rolling(w).mean()
        out[f'choppiness_{w}'] = 1-out[f'efficiency_{w}']
        out[f'range_expansion_{w}'] = out[f'range_{w}']/out[f'range_{w}'].shift(w).replace(0, np.nan)
        out[f'high_distance_{w}'] = 100*(c/h.rolling(w).max()-1)
        out[f'low_distance_{w}'] = 100*(c/lo.rolling(w).min()-1)
        prior_high, prior_low = h.rolling(w).max().shift(), lo.rolling(w).min().shift()
        out[f'breakout_up_{w}'] = (c>prior_high).astype(float).where(prior_high.notna())
        out[f'breakout_down_{w}'] = (c<prior_low).astype(float).where(prior_low.notna())
        out[f'failed_breakout_{w}'] = (((h>prior_high)&(c<prior_high))|((lo<prior_low)&(c>prior_low))).astype(float).where(prior_high.notna())
        if 'iv' in b:
            out[f'iv_change_{w}'] = b.iv-b.iv.shift(w)
        if 'premium' in b:
            out[f'premium_change_{w}'] = 100*(b.premium/b.premium.shift(w)-1)
    out.index += pd.Timedelta(minutes=1)
    out['market_available_second'] = out.index.asi8//10**9
    return out.replace([np.inf, -np.inf], np.nan)


class Regimes:
    """Fit independent thresholds using training sessions only, not future rows."""
    @staticmethod
    def direction_score(frame,scales):
        parts=[]
        for col,scale in scales.items():
            if col in frame:
                parts.append(np.tanh(pd.to_numeric(frame[col],errors='coerce')/max(scale,1e-9)))
        if 'efficiency_15' in frame and 'return_15' in frame:
            parts.append(frame.efficiency_15*np.sign(frame.return_15))
        return pd.concat(parts,axis=1).mean(axis=1) if parts else pd.Series(np.nan,index=frame.index)

    def fit(self, frame):
        d = frame.drop_duplicates(['underlying', 'second'])
        self.thresholds = {}
        for u, g in d.groupby('underlying'):
            scales={col:float(g[col].abs().quantile(.75)) for col in ['return_15','slope_5','persistence_15','vwap_distance_pct'] if col in g and g[col].notna().any()}
            values = self.direction_score(g,scales).abs().dropna()
            rv = g.get('rv_15', pd.Series(dtype=float)).dropna()
            self.thresholds[u] = {
                'direction': values.quantile([.33, .75]).tolist() if len(values) else [0., 0.],
                'volatility': rv.quantile([.25, .75]).tolist() if len(rv) else [0., 0.],
                'direction_scales':scales,
            }
        return self

    def transform(self, frame):
        f = frame.copy()
        f['direction_score']=np.nan
        for u,t in self.thresholds.items():
            mask=f.underlying.eq(u)
            f.loc[mask,'direction_score']=self.direction_score(f.loc[mask],t['direction_scales'])
        direction, volatility, change, structure = [], [], [], []
        for row in f.itertuples():
            t = self.thresholds.get(row.underlying)
            ret, rv = getattr(row, 'direction_score', np.nan), getattr(row, 'rv_15', np.nan)
            eff, expansion = getattr(row, 'efficiency_15', np.nan), getattr(row, 'range_expansion_5', np.nan)
            if t is None or not np.isfinite(ret):
                direction.append('unknown')
            else:
                mild, strong = t['direction']
                direction.append('sideways' if abs(ret)<=mild else ('strong_' if abs(ret)>=strong else 'mild_')+('up' if ret>0 else 'down'))
            if t is None or not np.isfinite(rv):
                volatility.append('unknown')
            else:
                low, high = t['volatility']
                volatility.append('low' if rv<=low else 'high' if rv>=high else 'normal')
            delta = getattr(row, 'rv_change_5', np.nan)
            change.append('unknown' if not np.isfinite(delta) else 'expanding' if delta>0 else 'contracting' if delta<0 else 'stable')
            structure.append('unknown' if not np.isfinite(eff) else 'persistent' if eff>=.6 else 'choppy' if eff<=.25 else 'mixed')
        f['direction_regime'] = direction
        f['volatility_regime'] = volatility
        f['volatility_transition'] = change
        f['structure_regime'] = structure
        return f


def strict_event_matches(actual, predicted, tolerance):
    """Maximum-cardinality ordered one-to-one matching for sorted event times."""
    a, p = sorted(map(int, actual)), sorted(map(int, predicted))
    i = j = 0
    pairs = []
    while i<len(a) and j<len(p):
        if p[j]<a[i]-tolerance:
            j += 1
        elif p[j]>a[i]+tolerance:
            i += 1
        else:
            pairs.append((a[i], p[j])); i += 1; j += 1
    return pairs
