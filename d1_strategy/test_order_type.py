"""Order type emitted by the engine: explicit, from a role table, never inferred (software validation)."""
import numpy as np, pytest
from d1_algo.engine import ROLES, ROLE_ORDER_TYPE, SELL_ROLES
from d1_algo.models import OrderRequest
from test_d1_algo import make, run, OPEN          # the existing fake-feed helpers
def test_every_role_has_an_explicit_order_type_and_no_extra_entries():
    assert set(ROLE_ORDER_TYPE) == set(ROLES) and all((m in ('num', 'h_', 'v_') or (m == 's_' and r.startswith('cycle_stop'))) and v in ('DAY', 'IOC') for r, (m, v) in ROLE_ORDER_TYPE.items())      # s_ only for the default-off cycle-stop candidate roles
    assert all(ROLE_ORDER_TYPE[r] == ('num', 'DAY') for r in SELL_ROLES) and ROLE_ORDER_TYPE['protective_wing_buy'] == ('h_', 'IOC') and ROLE_ORDER_TYPE['overnight_lump'] == ('v_', 'IOC')
def test_unmapped_role_raises_instead_of_defaulting():
    with pytest.raises(KeyError): ROLE_ORDER_TYPE['made_up_role']
def test_order_request_defaults_leave_validity_empty_not_guessed():
    r = OrderRequest('t', 0.0, 'CE', 24000.0, 1, 'SELL', 10.0, 'ladder_solo'); assert r.validity == '' and r.module == ''
def test_replayed_orders_carry_validity_and_module_for_every_order():
    eng, feed = make(lambda t: 24012.0 + 0.01 * (t - OPEN)); run(eng, feed, OPEN, OPEN + 2400); df = eng.orders_frame()
    assert len(df) > 20 and {'scheduled_straddle', 'opening_wing_buy', 'protective_wing_buy'} <= set(df.role) and set(df.validity) <= {'DAY', 'IOC'} and set(df.module) <= {'num', 'h_', 'v_'} and not df.validity.isin(['', None]).any()
    for role, g in df.groupby('role'): assert set(g.validity) == {ROLE_ORDER_TYPE[role][1]} and set(g.module) == {ROLE_ORDER_TYPE[role][0]}, role
