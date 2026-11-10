"""The box's health script pushes once per failure (`deploy/surface/recorder_health.sh`).

The real script runs under /bin/sh with stub `systemctl`, `journalctl`, `df`, `du` and `curl` on PATH and the
script's own test hooks: the conditions are injected, the clock is set, and a push is whatever the curl stub was
handed. Nothing here touches the network or the box.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "surface" / "recorder_health.sh"
T0 = 1_800_000_000
HALF_HOUR = 1800

STUBS = {
    "systemctl": "echo active\n",
    "journalctl": "exit 0\n",
    "df": 'printf "Avail\\n20971520\\n"\n',                      # 20 GB free, in KiB
    "du": 'printf "100\\t%s\\n" "$3"\n',
    "curl": """rc=${STUB_CURL_RC:-0}
title=""; prio=""; body=""
while [ $# -gt 0 ]; do
  case "$1" in
    -H) case "$2" in "Title: "*) title=${2#Title: } ;; "Priority: "*) prio=${2#Priority: } ;; esac; shift 2 ;;
    -d) body=$2; shift 2 ;;
    -m) shift 2 ;;
    *) shift ;;
  esac
done
printf '%s|%s|%s\\n' "$prio" "$title" "$body" >> "$STUB_CURL_OUT"
exit $rc
""",
}


class Box:
    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.bin = tmp / "bin"
        self.bin.mkdir()
        for name, body in STUBS.items():
            f = self.bin / name
            f.write_text("#!/bin/sh\n" + body)
            f.chmod(0o755)
        self.state, self.log, self.pushes = tmp / "health.state", tmp / "health.log", tmp / "pushes"
        (tmp / "env").write_text("QR_NTFY_TOPIC=test-topic\n")
        self.seen = 0

    def run(self, bad: str, now: int, curl_rc: int = 0) -> list[tuple[str, str, str]]:
        """One cron tick with these conditions wrong; returns the pushes attempted on this tick as (priority, title, body)."""
        env = {"PATH": f"{self.bin}:{os.environ['PATH']}", "QR_HEALTH_BAD": bad, "QR_HEALTH_NOW": str(now),
               "QR_HEALTH_STATE": str(self.state), "QR_HEALTH_LOG": str(self.log), "QR_HEALTH_ENV": str(self.tmp / "env"),
               "STUB_CURL_OUT": str(self.pushes), "STUB_CURL_RC": str(curl_rc)}
        subprocess.run(["/bin/sh", str(SCRIPT)], env=env, check=True, capture_output=True, text=True)
        lines = self.pushes.read_text().splitlines() if self.pushes.exists() else []
        new, self.seen = lines[self.seen:], len(lines)
        return [tuple(l.split("|", 2)) for l in new]


@pytest.fixture
def box(tmp_path):
    return Box(tmp_path)


def test_one_push_for_one_failure_then_a_quiet_all_clear(box):
    """The 10 November case: one failed surface snapshot sits in the two-hour window for four ticks."""
    first = box.run(" surface-failed:1", T0)
    assert [(p, t) for p, t, _ in first] == [("urgent", "recorder ALERT")]
    assert "WRONG: surface-failed:1" in first[0][2]
    for k in (1, 2, 3):
        assert box.run(" surface-failed:1", T0 + k * HALF_HOUR) == []           # was three more pushes
    clear = box.run("", T0 + 4 * HALF_HOUR)
    assert [(p, t) for p, t, _ in clear] == [("low", "recorder OK")]
    assert "was: surface-failed" in clear[0][2] and "WRONG" not in clear[0][2]
    assert not box.state.exists()
    assert box.run("", T0 + 5 * HALF_HOUR) == []                                # healthy and quiet
    # the log is written on every tick, in the form the desk sheet reads
    log = box.log.read_text().splitlines()
    assert len(log) == 6 and all(" recorders: reconnects/h " in l for l in log)
    assert [("WRONG" in l) for l in log] == [True, True, True, True, False, False]


def test_a_count_change_is_quiet_and_a_new_condition_pushes(box):
    assert len(box.run(" surface-failed:1", T0)) == 1
    assert box.run(" surface-failed:2", T0 + HALF_HOUR) == []                   # same condition, another count
    both = box.run(" surface-failed:2 reconnects/h:12", T0 + 2 * HALF_HOUR)
    assert [(p, t) for p, t, _ in both] == [("urgent", "recorder ALERT")] and "reconnects/h:12" in both[0][2]
    assert box.run(" reconnects/h:9", T0 + 3 * HALF_HOUR) == []                 # one cleared, the other lasts
    assert box.state.read_text().split() == [str(T0 + 2 * HALF_HOUR), "reconnects/h"]
    back = box.run(" surface-failed:1 reconnects/h:9", T0 + 4 * HALF_HOUR)      # a condition that cleared and returned
    assert [(p, t) for p, t, _ in back] == [("urgent", "recorder ALERT")]


def test_a_lasting_outage_is_pushed_again_once_a_day(box):
    down = " qr-pm-polymarket:inactive"
    assert len(box.run(down, T0)) == 1
    assert box.run(down, T0 + 86400 - HALF_HOUR) == []
    again = box.run(down, T0 + 86400)
    assert [(p, t) for p, t, _ in again] == [("high", "recorder still WRONG")]
    assert box.run(down, T0 + 86400 + HALF_HOUR) == []
    assert len(box.run(down, T0 + 2 * 86400)) == 1


def test_a_push_that_fails_to_send_is_retried(box):
    assert len(box.run(" disk:4GB", T0, curl_rc=22)) == 1                       # attempted, refused
    assert not box.state.exists()                                               # so not recorded as told
    assert len(box.run(" disk:4GB", T0 + HALF_HOUR, curl_rc=22)) == 1           # attempted again
    assert len(box.run(" disk:4GB", T0 + 2 * HALF_HOUR)) == 1                   # sent
    assert box.run(" disk:4GB", T0 + 3 * HALF_HOUR) == []                       # and quiet from here
    assert len(box.run("", T0 + 4 * HALF_HOUR, curl_rc=22)) == 1                # the all-clear fails to send
    assert box.state.exists()
    assert [(p, t) for p, t, _ in box.run("", T0 + 5 * HALF_HOUR)] == [("low", "recorder OK")]
    assert not box.state.exists()
