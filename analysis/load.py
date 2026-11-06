import pandas as pd, numpy as np
import os
RAW=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','Trades_GKOHNP140.csv')
def load():
    r = pd.read_csv(RAW, header=None, dtype=str, keep_default_na=False)
    d = pd.DataFrame({
        'status_code': r[1], 'seg': r[3], 'oid': r[4], 'side': r[11], 'und': r[12],
        'strike': pd.to_numeric(r[14]), 'expiry_txt': r[15], 'cp': r[16],
        'px_order': pd.to_numeric(r[17]), 'px_fill': pd.to_numeric(r[18]),
        'qty_order': pd.to_numeric(r[19]), 'qty_c20': pd.to_numeric(r[20]),
        'validity': r[22], 'ts_order_txt': r[23], 'status': r[27], 'tradeid': r[28],
        'qty_fill': pd.to_numeric(r[33]), 'desc': r[32],
        'px137': pd.to_numeric(r[137]), 'ts_c69': r[69], 'ts_c78': r[78], 'ts_c130': r[130],
        'epoch_exp': pd.to_numeric(r[158]), 'epoch_trade': pd.to_numeric(r[161]),
        'c126': r[126], 'c144': r[144], 'c145': r[145], 'c147': r[147], 'c163': r[163], 'c166': r[166], 'c154': r[154],
    })
    d['row']=np.arange(len(d))
    d['t'] = pd.to_datetime(d.epoch_trade, unit='s') + pd.Timedelta(hours=5, minutes=30)
    d['date']=d.t.dt.normalize()
    d['expiry']=pd.to_datetime(d.desc.str.split().str[1], format='%d%b%Y')
    d['lot']=np.where(d.und=='NIFTY',65,20)
    d['lots']=d.qty_fill/d.lot
    d['dte']=(d.expiry-d.date).dt.days
    d['dow']=d.date.dt.day_name().str[:3]
    d['hhmm']=d.t.dt.strftime('%H:%M')
    d['sgn']=np.where(d.side=='Buy',1,-1)
    return d
