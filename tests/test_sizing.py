import pytest

from centaur.sizing import position_size


def test_worked_example_from_rulebook():
    ps = position_size(10_000, 0.01, 150, 145)
    assert ps.shares == 20 and ps.max_risk_dollars == 100 and ps.actual_risk_dollars == 100


def test_rounds_down_never_up():
    ps = position_size(10_000, 0.01, 150, 147)   # 100/3 = 33.3
    assert ps.shares == 33 and ps.actual_risk_dollars <= 100


@pytest.mark.parametrize("kw", [dict(equity=0), dict(risk_pct=0.5), dict(stop=150), dict(entry=-1)])
def test_invalid_inputs(kw):
    base = dict(equity=10_000, risk_pct=0.01, entry=150, stop=145)
    base.update(kw)
    with pytest.raises(ValueError):
        position_size(**base)
