"""Decision-time feature timing (remediation of defect D). A decision/feature at minute j of day d may use only bars that have COMPLETED: bar j-1 of the same day, or, at the first minute of D0 (j=0), the last bar of D-1.
At the first minute of D-1 there is no completed bar: the feature is NaN (the legacy build_events.py used the same-minute close, which is look-ahead for orders placed in the 09:15 minute)."""
import numpy as np
NM = 375


def prev_bar(day_index, j):
    """-> (day_index_of_bar, bar_index) of the last completed bar before minute j of `day_index` (0 = D-1, 1 = D0), or None"""
    if j > 0: return day_index, min(j - 1, NM - 1)
    if day_index == 1: return 0, NM - 1
    return None


def prev_value(arrays, day_index, j, row):
    """arrays[(day, 'close')][row, bar]-style access: arrays is a dict {(day): 2-D array}; returns NaN if no completed bar"""
    pb = prev_bar(day_index, j)
    return np.nan if pb is None else arrays[pb[0]][row, pb[1]]


def prev_spot(spots, day_index, j):
    pb = prev_bar(day_index, j)
    return np.nan if pb is None else spots[pb[0]][pb[1]]
