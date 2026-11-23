"""Run the engine on a synthetic day with the paper broker and print what it did.   python run_paper_example.py"""
import time
from d1_algo import PaperBroker, ReplayFeed, D1Engine, config_for, run_replay
from d1_algo.engine import ROLES
from example_synthetic import make_day

o, h, l, c, chain = make_day(seed=7)
feed = ReplayFeed(o, h, l, c, chain.strikes, chain.bars); broker = PaperBroker(feed)
engine = D1Engine(config_for("NIFTY", "2026-07-01"), feed, broker)
t0 = time.time(); run_replay(engine, feed)
df = engine.orders_frame()
print(f"replayed one session in {time.time() - t0:.1f}s\n")
print(df.groupby("role").agg(orders=("lots", "size"), lots=("lots", "sum")).to_string())
print("\nend-of-day short lots :", {r: engine.book.short_count(r, False) for r in ("CE", "PE")})
print("end-of-day wing lots  :", {r: engine.book.wing_count(r, False) for r in ("CE", "PE")})
print("overnight lump        :", engine.book.lump)
print("blocked by risk guard :", len(engine.rejected))
print("\nrole glossary:"); [print(f"  {k:22s} {v}") for k, v in ROLES.items()]
