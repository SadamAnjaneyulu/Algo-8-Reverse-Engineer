from __future__ import annotations
from dataclasses import dataclass, field

SESSION_OPEN_S = 9 * 3600 + 15 * 60          # 09:15:00 in seconds since midnight; minute index 0 = 09:15


def minute_index(t: float) -> int:
    return int((t - SESSION_OPEN_S) // 60)


@dataclass(frozen=True)
class OrderRequest:
    """One order sent to the broker. lots is a number of lots (not units). side: 'BUY' or 'SELL'."""
    tag: str                                  # unique id of this order (idempotency key)
    ts: float                                 # seconds since midnight when the engine created it
    right: str                                # 'CE' or 'PE'
    strike: float
    lots: int
    side: str
    limit_price: float
    role: str                                 # why the order exists, see ROLES in engine.py
    validity: str = ""                       # 'DAY' or 'IOC', set explicitly from ROLE_ORDER_TYPE (never inferred; empty only for orders built outside the engine)
    module: str = ""                         # order-tag module of the original system: 'num' body, 'h_' wing, 'v_' lump
    decision_id: str = ""                    # one id per strategy decision (one _submit call): every child order of a split decision carries the same id; independent decisions never share one


@dataclass
class Fill:
    tag: str
    ts: float
    right: str
    strike: float
    lots: int
    side: str
    price: float
    role: str


@dataclass
class Lot:
    """One short lot in the book. minute = minute index in which it was sold (a lot cannot be stopped in the minute it is sold)."""
    ts: float
    minute: int
    entry_price: float
    role: str
