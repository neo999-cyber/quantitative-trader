# S1 implementation — variant s1_h252_d0: hold 252, delay 0, mode deletion
# S1 implementation (docs/prereg/p2_index_deletion_v1.md), loaded by qc/bootstrap_main.py:
# every top-level function taking `self` is bound to the running QCAlgorithm.
# Selection is done offline (scripts/s1_events.py, no prices); this only executes:
# on the first session after `avail_date` (the change's effective date, when index
# funds sold at the close), buy the `mode` names at the open, hold `hold` sessions.
import base64, hashlib, zlib
from datetime import datetime, timedelta

EVENTS_URL = "https://raw.githubusercontent.com/neo999-cyber/quantitative-trader/claude/funny-faraday-nizzck/qc/s1_events.b64"
EVENTS_SHA256_PREFIX = "5bd5190b425da40f"
HOLD = 252
MODE = 'deletion'
SLOTS = 10          # concurrent names the book is divided into
DELAY = 0


def impl_initialize(self):
    self.set_start_date(2008, 1, 2)
    self.set_end_date(int(self.get_parameter("end_year", "2025")), 8, 29)
    self.set_cash(int(self.get_parameter("equity", "1000")))
    self.hold = int(self.get_parameter("hold", str(HOLD)))
    self.mode = self.get_parameter("mode", MODE)
    self.slots = int(self.get_parameter("slots", str(SLOTS)))
    self.delay = int(self.get_parameter("delay", str(DELAY)))
    self.entry_cutoff = datetime.strptime(self.get_parameter("entry_cutoff", "2024-08-31"), "%Y-%m-%d").date()
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
        avail, sym, mode, rank = r.split(",")
        if mode != self.mode:
            continue
        d = datetime.strptime(avail, "%Y-%m-%d").date()
        if d < self.start_date.date() or d > self.entry_cutoff:
            continue
        self.by_day.setdefault(d, []).append((sym, int(rank)))
        n += 1
    self.debug(f"events {n} on {len(self.by_day)} days, mode {self.mode}, hold {self.hold}, slots {self.slots}, delay {self.delay}")
    self.pending = []        # (symbol, rank, enter_at_session)
    self.open_positions = {}
    self.session = 0
    self.schedule.on(self.date_rules.every_day(), self.time_rules.at(9, 25), self.before_open)
    self.schedule.on(self.date_rules.every_day(), self.time_rules.at(16, 5), self.after_close)


def after_close(self):
    d = self.time.date()
    # a change effective today (or over a weekend since the last session) is bought at the next open
    for back in range(0, 4):
        day = d - timedelta(days=back)
        for sym, rank in self.by_day.pop(day, []):
            try:
                sec = self.add_equity(sym, Resolution.DAILY)
            except Exception:
                continue
            self.pending.append((sec.symbol, rank, self.session + 1 + self.delay))
    self.session += 1


def before_open(self):
    for sym, exit_at in list(self.open_positions.items()):
        if self.session >= exit_at:
            self.market_on_open_order(sym, -self.portfolio[sym].quantity)
            del self.open_positions[sym]
    due = [p for p in self.pending if p[2] <= self.session]
    self.pending = [p for p in self.pending if p[2] > self.session]
    due.sort(key=lambda q: q[1])
    for sym, rank, _ in due:
        sec = self.securities[sym]
        if sym in self.open_positions or not sec.has_data or sec.price <= 0:
            continue
        price = float(sec.price)
        if price < 1:
            continue
        # each name gets one slot of the book; a full book skips the name (it is logged, not queued)
        if len(self.open_positions) >= self.slots:
            self.debug(f"skip {sym.value}: book full on session {self.session}")
            continue
        qty = int((self.portfolio.total_portfolio_value / self.slots) // price)
        if qty < 1:
            self.debug(f"skip {sym.value}: one slot buys no whole share at {price:.2f}")
            continue
        self.market_on_open_order(sym, qty)
        self.open_positions[sym] = self.session + self.hold
