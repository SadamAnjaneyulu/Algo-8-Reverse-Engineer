import os, sys
import numpy as np, pandas as pd, pytest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts'))
import tp02_common as c
need_data = pytest.mark.skipif(not os.path.exists(os.path.join(c.DATA, 'exit_event_mechanisms.parquet')), reason='TP-02 outputs not built (run run_tp02.py)')


@pytest.fixture(scope='session')
def T(): return pd.read_parquet(os.path.join(c.DATA, 'exit_event_mechanisms.parquet'))
@pytest.fixture(scope='session')
def TL(): return pd.read_parquet(os.path.join(c.DATA, 'exit_event_timelines.parquet'))
@pytest.fixture(scope='session')
def X01(): return c.tp01('exit_event_consensus.parquet')
