"""Label-alignment primitives (Milestone 1: definitions and tests only; no target is evaluated here).

Convention (same as the PR #6 feature library):
  * a feature row keyed by decision minute m uses only bars whose START is <= m - 1 minute (bars completed before m);
  * a label for decision minute m and horizon h uses only bars whose START is in [m, m + h - 1], i.e. it begins strictly after the signal;
  * labels never cross the session end: a decision minute is valid for horizon h only if m + h - 1 <= 15:29.
Session minute index k: 0 = the 09:15 bar ... 374 = the 15:29 bar.  A decision at minute m has index kd = minutes(m - 09:15)."""
import numpy as np

N = 375


def feature_bars(kd):
    """indices of the bars a feature row at decision index kd may use (same session)"""
    return np.arange(0, max(kd, 0))


def label_bars(kd, h, n=N):
    """indices of the bars a label at decision index kd with horizon h uses; empty if the window does not fit in the session"""
    if kd < 0 or h < 1 or kd + h > n: return np.arange(0)
    return np.arange(kd, kd + h)


def valid_decisions(h, n=N, first=1):
    """decision indices with a complete label window (kd >= first: at least one completed bar exists before the decision)"""
    return np.arange(first, n - h + 1)


def non_overlapping_decisions(h, n=N, first=1):
    """decision indices spaced h apart: their label windows do not overlap"""
    return np.arange(first, n - h + 1, h)


def purge_radius(h):
    """two decisions in one session have overlapping label windows iff they are closer than h minutes"""
    return h
