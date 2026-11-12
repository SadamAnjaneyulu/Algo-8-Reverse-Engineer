"""Chronological, date-clustered validation design (LOCKED at Milestone 2, decision D3).  Nothing is ever shuffled.

  primary folds     : the sorted session dates are cut into TRAIN (first 43), VAL (next 22), TEST (final 20)
  stability blocks  : four contiguous date blocks; expanding step k (k = 1..3): fit on blocks 1..k, evaluate on block k+1
  cluster           : the session date.  NIFTY and SENSEX rows of one date always share a fold / block / bootstrap draw
  purge             : inside a session only decisions on the non-overlapping grid kd = (h + 1) + phase + j*h are used, so no two label windows overlap.
                      Labels never cross a session, so no observation has to be purged between date folds."""
import numpy as np, pandas as pd
N = 375


def primary_folds(dates, sizes):
    d = sorted(pd.to_datetime(pd.Series(list(dates)).unique())); n = [sizes['train'], sizes['validation'], sizes['test']]
    assert sum(n) == len(d), (sum(n), len(d))
    lab = ['TRAIN'] * n[0] + ['VAL'] * n[1] + ['TEST'] * n[2]
    return pd.Series(lab, index=pd.DatetimeIndex(d), name='fold')


def stability_blocks(dates, k=4):
    d = sorted(pd.to_datetime(pd.Series(list(dates)).unique())); parts = np.array_split(np.arange(len(d)), k)
    lab = np.concatenate([[i + 1] * len(p) for i, p in enumerate(parts)])
    return pd.Series(lab, index=pd.DatetimeIndex(d), name='block')


def grid(h, phase=0, n=N):
    """non-overlapping decision indices for horizon h: first decision at h + 1 + phase (a full trailing window of h completed bars exists), spacing h"""
    assert 0 <= phase < h
    return np.arange(h + 1 + phase, n - h + 1, h)


def valid_range(h, n=N):
    """every decision index with a complete trailing window and a complete label window (before purging)"""
    return np.arange(h + 1, n - h + 1)
