# E7 implementation — variant e7_n10_h10 10 10 top: n , hold , mode 
# E7 implementation (docs/prereg/p2_short_squeeze_v1.md + amendment), loaded by qc/bootstrap_main.py:
# every top-level function taking `self` is bound to the running QCAlgorithm.
# Selection is done offline (scripts/e7_events.py, no prices); this only executes:
# on the first session after `avail_date`, buy the first `n` names of `mode` at the open, hold `hold` sessions.
import base64, hashlib, zlib
from datetime import datetime, timedelta

EVENTS_URL = "https://raw.githubusercontent.com/neo999-cyber/quantitative-trader/claude/funny-faraday-nizzck/qc/e7_events.b64"
EVENTS_SHA256_PREFIX = "e469af595960c4bb"
N = 
HOLD = 
MODE = ""   # top | bottom | random


def impl_initialize(self):
    self.set_start_date(2019, 1, 2)
    self.set_end_date(2025, 8, 29)
    self.set_cash(int(self.get_parameter("equity", "1000")))
    self.n = int(self.get_parameter("n", str(N)))
    self.hold = int(self.get_parameter("hold", str(HOLD)))
    self.mode = self.get_parameter("mode", MODE)
    self.set_security_initializer(lambda s: s.set_fee_model(ConstantFeeModel(0)))
    self.universe_settings.resolution = Resolution.DAILY
    raw = self.download(EVENTS_URL)
    csv = zlib.decompress(base64.b64decode(raw)).decode()
    digest = hashlib.sha256(csv.encode()).hexdigest()
    if not digest.startswith(EVENTS_SHA256_PREFIX):
        raise ValueError("event file hash mismatch: " + digest[:16])
    self.by_day = {}
    n = 0
    for r in csv.strip().splitlines()[1:]:
        avail, sym, mode, rank, _ = r.split(",")
        if mode != self.mode or int(rank) > self.n:
            continue
        d = datetime.strptime(avail, "%Y-%m-%d").date()
        self.by_day.setdefault(d, []).append((sym, int(rank)))
        n += 1
    self.debug(f"events {n} on {len(self.by_day)} days, mode {self.mode}, n {self.n}, hold {self.hold}")
    self.pending = []        # (symbol, rank) to enter at the next open
    self.open_positions = {}
    self.session = 0
    self.schedule.on(self.date_rules.every_day(), self.time_rules.at(9, 25), self.before_open)
    self.schedule.on(self.date_rules.every_day(), self.time_rules.at(16, 5), self.after_close)


def after_close(self):
    d = self.time.date()
    # files that became available today or on the days since the last session enter at the next open
    for back in range(0, 4):
        day = d - timedelta(days=back)
        for sym, rank in self.by_day.pop(day, []):
            try:
                sec = self.add_equity(sym, Resolution.DAILY)
            except Exception:
                continue
            self.pending.append((sec.symbol, rank))
    self.session += 1


def before_open(self):
    for sym, exit_at in list(self.open_positions.items()):
        if self.session >= exit_at:
            self.market_on_open_order(sym, -self.portfolio[sym].quantity)
            del self.open_positions[sym]
    due = self.pending
    self.pending = []
    due.sort(key=lambda q: q[1])
    # a publication's names get equal slices of the book; an unexpired earlier
    # publication keeps its positions, so the book can briefly hold up to 2n
    slots = self.n
    for sym, rank in due:
        sec = self.securities[sym]
        if sym in self.open_positions or not sec.has_data or sec.price <= 0:
            continue
        price = float(sec.price)
        if price < 5:
            continue
        qty = int((self.portfolio.total_portfolio_value / slots) // price)
        if qty < 1:
            continue
        self.market_on_open_order(sym, qty)
        self.open_positions[sym] = self.session + self.hold
