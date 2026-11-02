"""The P5 run script end to end on fixtures: the real arm classes on stand-in models (so the attribute surface is the
real one), a scratch QR_ROOT, no lake, no weights, no trial log. The money-test path is forced so the tail runs too."""
import importlib
import json
import sys
from pathlib import Path

import pandas as pd

from qr.data.panel import Panel
from qr.research import forecast as fc
from qr.research import tsfm
from test_forecast import _inputs
from test_tsfm import _FakeTimesFM3, _FakeTimesFM25


def _p5():
    scripts = str(Path(__file__).resolve().parents[2] / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module("p5_tsfm_forecast")


def test_run_script_end_to_end_on_fixtures(monkeypatch, tmp_path):
    p5 = _p5()
    df = _inputs(n=1600)
    monkeypatch.setenv("QR_ROOT", str(tmp_path / "lake"))
    monkeypatch.setattr(fc, "load_inputs", lambda lake, mirror: df)
    fake3 = _FakeTimesFM3()

    def build(names, backend="auto"):
        return {"timesfm3": tsfm.TimesFM3Arm(forecaster=fake3, backend="stand-in"),
                "timesfm3_cov": tsfm.TimesFM3Arm(covariates=True, forecaster=fake3, backend="stand-in"),
                "timesfm25": tsfm.TimesFM25Arm(model=_FakeTimesFM25())}

    class StubLake:
        def __init__(self, p):
            pass

        def load_panel(self, symbols, interval, start=None, market=None):
            c = df["close"].rename("BTCUSDT").to_frame()
            vol = pd.DataFrame({"BTCUSDT": 1e5}, index=df.index)
            return Panel({"close": c, "open": c, "high": c * 1.01, "low": c * 0.99, "volume": vol, "quote_volume": vol * c.values}, "1d")

    monkeypatch.setattr(p5, "build_arms", build)
    monkeypatch.setattr(p5, "Lake", StubLake)
    monkeypatch.setattr(p5, "passes_bar", lambda target, sc: True)     # force the money-test and research-finding paths
    assert p5.main(["--no-log"]) == 0
    out = tmp_path / "lake" / "reports" / "p5"
    summary = json.loads((out / "p5_insample_summary.json").read_text())
    assert len(summary["results"]) == 9 and summary["n_forecasts"] > 0
    assert set(summary["gates"]["money_tested"]) == {"direction:timesfm25", "ret7:timesfm25"}      # the licence rule
    assert summary["verdict"]["research_findings_no_money_test"] == [n for n in summary["verdict"]["statistical_passes"] if "timesfm3" in n]
    assert summary["arms"]["timesfm25"]["backend"] == "torch" and summary["arms"]["timesfm3_cov"]["covariates"]
    assert "Non-Commercial" in summary["arms"]["timesfm3"]["licence"] and summary["arms"]["timesfm25"]["licence"] == "Apache-2.0"
    # the covariate arm was fed the 43 features, one column per history point, never a row after the forecast day
    cov_calls = [c for c in fake3.calls if c["cov"] is not None]
    assert cov_calls and all(c["cov"].shape == (43, len(c["context"])) for c in cov_calls)
    assert len(list((out / "cache").glob("*.parquet"))) == 27 and (out / "p5_insample_report.md").exists()
    # a second start resumes from the checkpoints without asking the arms for a single forecast
    n_calls = len(fake3.calls)
    assert p5.main(["--no-log"]) == 0
    assert len(fake3.calls) == n_calls
