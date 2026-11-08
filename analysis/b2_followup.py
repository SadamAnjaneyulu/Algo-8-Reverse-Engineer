"""B2c: for decisions where indicators added OOS signal (D3 strike off-ATM, D7 leg-stop executed), (1) give D7 a raw-price baseline,
(2) ablate indicator FAMILIES (each family alone on top of base+price) vs 3 date-derangement nulls.   python3 analysis/b2_followup.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
import b2_indicator_tests as B
C = B.C
ix = pd.read_pickle(os.path.join(C, 'idx_candles.pkl')).set_index(['und', 'ts']).close.sort_index()
FAM = {'trend': ['ema', 'sma', 'macd', 'supertrend', 'adx', 'di_diff'], 'oscillator': ['rsi', 'stoch', 'cci', 'roc'],
       'volatility': ['atr', 'bb_width', 'rv20', 'day_range'], 'bands': ['bb_pctb'],
       'levels': ['dist_prev', 'dist_pivot', 'dist_R1', 'dist_S1', 'dist_day', 'gap_bp', 'orb'],
       'options': ['atm_iv', 'iv_ce', 'straddle', 'skew', 'pcr']}
def fam_cols(f): return [c for c in B.IND_COLS if any(k in c for k in FAM[f])]
def add_price(df):
    sg = np.where(df.ce == 1, 1, -1)
    for L in [1, 5, 15]:
        a = np.array([ix.get((u, m - pd.Timedelta(minutes=1)), np.nan) for u, m in zip(df.und, df.m)])
        b = np.array([ix.get((u, m - pd.Timedelta(minutes=1 + L)), np.nan) for u, m in zip(df.und, df.m)])
        df[f'pmv{L}'] = (a - b) / a * 1e4 * sg
    return df, ['pmv1', 'pmv5', 'pmv15']
if __name__ == '__main__':
    rng = np.random.default_rng(3); maps = [B.derangement_map(rng) for _ in range(3)]
    D = B.datasets(); out = []
    for name in ['D3 strike offset != ATM (sale)', 'D7 leg stop executed vs survived', 'D3b offset direction (OTM vs ITM)']:
        df, base, price, side = D[name]; df = df.dropna(subset=['label']).reset_index(drop=True)
        if not price: df, price = add_price(df)
        dates = pd.to_datetime(df.date); y = df.label.astype(int)
        Xp = df[base + price].astype(float); a_p = B.oos_auc(Xp, y, dates)
        real = B.attach(df, side); nulls = [B.attach(df, side, mp) for mp in maps]
        a_all = B.oos_auc(pd.concat([Xp, real], axis=1), y, dates)
        out.append(dict(decision=name, family='(none: base+price)', auc=round(a_p, 3), gain=0, null_max_gain=np.nan))
        out.append(dict(decision=name, family='ALL indicators', auc=round(a_all, 3), gain=round(a_all - a_p, 3),
                        null_max_gain=round(max(B.oos_auc(pd.concat([Xp, n], axis=1), y, dates) for n in nulls) - a_p, 3)))
        for f in FAM:
            cols = fam_cols(f)
            a = B.oos_auc(pd.concat([Xp, real[cols]], axis=1), y, dates)
            nm = max(B.oos_auc(pd.concat([Xp, n[cols]], axis=1), y, dates) for n in nulls)
            out.append(dict(decision=name, family=f, auc=round(a, 3), gain=round(a - a_p, 3), null_max_gain=round(nm - a_p, 3)))
            print(out[-1], flush=True)
    R = pd.DataFrame(out); R['real_signal'] = (R.gain > 0.005) & (R.gain > R.null_max_gain)
    R.to_csv(os.path.join(C, 'b2_followup.csv'), index=False); pd.set_option('display.width', 200); print(R.to_string(index=False))
