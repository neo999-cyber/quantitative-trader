import json

from centaur.rules.candidate import TradeCandidate, Signal, SignalCategory


def test_roundtrip(tmp_path):
    c = TradeCandidate("MSFT", 400.0, 390.0, 430.0, signals=[Signal(SignalCategory.FUNDAMENTAL, "guidance raise", "human")],
                       catalyst="guide up", avg_dollar_volume=8e9, resistance_levels=[420.0])
    p = tmp_path / "c.json"
    c.save(p)
    back = TradeCandidate.load(p)
    assert back.to_dict() == c.to_dict()


def test_from_dict_accepts_string_signals_and_unknown_fields(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"ticker": "nvda", "entry": 100, "stop": 95, "target": 115, "direction": "LONG",
                             "signals": ["technical: 200dma bounce", "sentiment_flow: insider buying", "no category here"],
                             "bogus": 1}))
    c = TradeCandidate.load(p)
    assert c.ticker == "nvda" and c.direction.value == "long"
    assert [s.category.value for s in c.signals] == ["technical", "sentiment_flow", "technical"]
    assert "ignored fields" in c.notes
