"""Template for running the engine live. Implement MyFeed and MyBroker for the broker/data vendor in use, then run this file.

NOTHING HERE TALKS TO A BROKER: the two adapter classes raise NotImplementedError on purpose. Test every adapter method against the broker's paper or
sandbox environment first. The engine refuses to run unpaper unless the environment variable D1_ALLOW_LIVE=1 is set.
"""
from __future__ import annotations
import datetime as dt
import logging
import os
import time
from typing import Dict, List, Tuple
import numpy as np

from d1_algo import D1Engine, config_for
from d1_algo.models import Fill, OrderRequest, SESSION_OPEN_S

log = logging.getLogger("d1")


class MyFeed:
    """MarketData adapter. now() must be exchange time in seconds since midnight. spot()/option_ltp() should return the latest traded price from a
    streaming subscription (not a REST poll every second). Subscribe to the index and to every listed strike of the expiry being traded, both rights."""
    def now(self) -> float:
        n = dt.datetime.now(); return n.hour * 3600 + n.minute * 60 + n.second + n.microsecond / 1e6
    def spot(self) -> float: raise NotImplementedError
    def option_ltp(self, right: str, strike: float) -> float: raise NotImplementedError
    def strikes(self) -> np.ndarray: raise NotImplementedError
    def spot_history(self) -> List[Tuple[float, float, float, float]]:
        """Completed one-minute index bars (open, high, low, close) since 09:15, for a mid-session restart."""
        raise NotImplementedError


class MyBroker:
    """Broker adapter. place() sends a LIMIT order and returns [] (the fill arrives later through poll_fills()); poll_fills() returns the Fill records
    for orders confirmed since the last call, using OrderRequest.tag as the client order id so a repeated call can never create a second order."""
    def place(self, req: OrderRequest) -> List[Fill]: raise NotImplementedError
    def poll_fills(self) -> List[Fill]: raise NotImplementedError
    def positions(self) -> Dict[Tuple[str, float], int]: raise NotImplementedError


def main(underlying: str, d1_date: str, state_file: str = "d1_state.json", kill_file: str = "d1_STOP"):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = config_for(underlying, d1_date, paper=False, state_file=state_file, kill_switch_file=kill_file, max_loss_rupees=None)
    if not cfg.paper and os.environ.get("D1_ALLOW_LIVE") != "1":
        raise SystemExit("Live mode needs D1_ALLOW_LIVE=1. Run the paper setup first.")
    feed, broker = MyFeed(), MyBroker()
    eng = D1Engine(cfg, feed, broker, log=log.info)
    if os.path.exists(state_file): eng.load()                                  # restart: restore book, done waves, ladder references, bars
    else: eng.warm_start(feed.spot_history()) if feed.now() > SESSION_OPEN_S + 60 else None
    # reconcile: after a restart compare eng.book with broker.positions() and stop if they differ
    log.info("start %s %s positions=%s", underlying, d1_date, broker.positions())
    while feed.now() < SESSION_OPEN_S + 60 * 391:                               # until about 15:41
        t0 = time.time()
        try:
            eng.step()
        except Exception:                                                       # never die silently: log, keep protecting
            log.exception("step failed")
        time.sleep(max(0.0, 1.0 - (time.time() - t0)))
    eng.save(); log.info("done; book=%s", eng.book.snapshot())


if __name__ == "__main__":
    main("NIFTY", "2026-09-08")
