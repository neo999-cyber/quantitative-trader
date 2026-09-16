# E4: post-earnings-announcement drift, long-only (docs/prereg/p2_pead_v1.md).
from AlgorithmImports import *
from datetime import datetime, timedelta
import base64, hashlib, random, zlib

EVENTS_URL = "https://raw.githubusercontent.com/neo999-cyber/quantitative-trader/claude/funny-faraday-nizzck/qc/e4_events.b64"
EVENTS_SHA256_PREFIX = "36cf322ba5daf79e"


class PeadE4(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2010, 1, 4)
        self.set_end_date(2025, 8, 29)
        self.set_cash(int(self.get_parameter("equity", "1000")))
        self.hold = int(self.get_parameter("hold", "60"))
        self.top = float(self.get_parameter("top", "0.10"))
        self.max_positions = int(self.get_parameter("max_positions", "4"))
        self.max_cap = float(self.get_parameter("max_cap_usd", "10000000000"))
        self.window = int(self.get_parameter("window", "250"))
        self.mode = self.get_parameter("mode", "top")   # top | bottom | random
        self.rng = random.Random(1)
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
            sym, stamp = r.split(",")
            acc = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=4)
            d = acc.date()
            after_close = acc.hour >= 16
            self.by_day.setdefault(d, []).append((sym, after_close))
            n += 1
        self.debug(f"events {n} on {len(self.by_day)} days")
        self.watch = []          # (symbol, announcement_session_index)
        self.recent = []         # announcement returns of the trailing window
        self.pending_entry = []  # (symbol, ann_return) to enter at the next open
        self.open_positions = {}
        self.session = 0
        self.prev_close = {}
        self.schedule.on(self.date_rules.every_day(), self.time_rules.at(9, 25), self.before_open)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.at(16, 5), self.after_close)

    def after_close(self):
        d = self.time.date()
        # events whose acceptance fell today (before the close) or on the days since the last session
        for back in range(0, 4):
            day = d - timedelta(days=back)
            for sym, after_close in self.by_day.pop(day, []):
                try:
                    sec = self.add_equity(sym, Resolution.DAILY)
                except Exception:
                    continue
                # announcement session: today if accepted before today's close, else the next session
                ann = self.session if (back == 0 and not after_close) else self.session + 1
                self.watch.append((sec.symbol, ann))
        self.session += 1

    def rank_events(self):
        # at 09:25 of session s the daily bar of session s-1 is in; announcement
        # returns for events whose announcement session was s-1 are observable now
        still = []
        for sym, ann in self.watch:
            if ann > self.session - 1:
                still.append((sym, ann)); continue
            if ann < self.session - 1:
                continue
            sec = self.securities[sym]
            hist = self.history(sym, 3, Resolution.DAILY)
            if hist.empty or "close" not in hist.columns or len(hist) < 2:
                continue
            closes = hist["close"]
            ann_ret = float(closes.iloc[-1] / closes.iloc[-2] - 1.0)
            self.recent.append(ann_ret)
            self.recent = self.recent[-self.window:]
            if len(self.recent) < 50:
                continue
            ranked = sorted(self.recent)
            if self.mode == "top":
                fire = ann_ret >= ranked[int((1 - self.top) * (len(ranked) - 1))]
            elif self.mode == "bottom":
                fire = ann_ret <= ranked[int(self.top * (len(ranked) - 1))]
            else:
                fire = self.rng.random() < self.top
            if fire:
                self.pending_entry.append((sym, ann_ret))
        self.watch = still

    def before_open(self):
        self.rank_events()
        for sym, exit_at in list(self.open_positions.items()):
            if self.session >= exit_at:
                self.market_on_open_order(sym, -self.portfolio[sym].quantity)
                del self.open_positions[sym]
        due = self.pending_entry
        self.pending_entry = []
        due.sort(key=lambda q: -q[1])
        room = self.max_positions - len(self.open_positions)
        for sym, ann_ret in due:
            if room <= 0:
                break
            sec = self.securities[sym]
            if sym in self.open_positions or not sec.has_data or sec.price <= 0:
                continue
            hist = self.history(sym, 21, Resolution.DAILY)
            if hist.empty or "close" not in hist.columns or "volume" not in hist.columns or len(hist) < 20:
                continue
            closes = hist["close"]; vols = hist["volume"]
            price = float(closes.iloc[-1])
            dollar = float((closes * vols).median())
            cap = None
            try:
                cap = float(sec.fundamentals.market_cap) if sec.fundamentals is not None else None
            except Exception:
                cap = None
            if price < 5 or dollar < 5e6 or (cap is not None and cap > self.max_cap):
                continue
            qty = int((self.portfolio.total_portfolio_value / self.max_positions) // price)
            if qty < 1:
                continue
            self.market_on_open_order(sym, qty)
            self.open_positions[sym] = self.session + self.hold
            room -= 1
