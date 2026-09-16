# E5: insider cluster purchases, long-only (docs/prereg/p2_insider_cluster_v1.md).
# Runs on QuantConnect's free tier. Signals come from e5_signals.py (a project file,
# because data files are not readable there); results leave as the daily equity log.
from AlgorithmImports import *
from datetime import datetime, timedelta
import base64, hashlib, zlib

SIGNALS_URL = "https://raw.githubusercontent.com/neo999-cyber/quantitative-trader/claude/funny-faraday-nizzck/qc/e5_signals.b64"
SIGNALS_SHA256_PREFIX = "ad8442109fd2323e"  # of the decoded CSV; a corrupted download stops the run


class InsiderClusterE5(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2010, 1, 4)
        self.set_end_date(2025, 8, 29)          # in-sample; the holdout year is opened once, later
        self.set_cash(int(self.get_parameter("equity", "1000")))
        self.hold = int(self.get_parameter("hold_sessions", "60"))
        self.min_combined = float(self.get_parameter("min_combined_usd", "100000"))
        self.min_insiders = int(self.get_parameter("min_insiders", "2"))
        self.max_positions = int(self.get_parameter("max_positions", "4"))
        self.set_brokerage_model(BrokerageName.ALPACA, AccountType.CASH)
        self.settings.minimum_order_margin_portfolio_percentage = 0
        self.universe_settings.resolution = Resolution.DAILY
        self.set_security_initializer(lambda s: s.set_fee_model(ConstantFeeModel(0)))

        raw = self.download(SIGNALS_URL)
        csv = zlib.decompress(base64.b64decode(raw)).decode()
        digest = hashlib.sha256(csv.encode()).hexdigest()
        if not digest.startswith(SIGNALS_SHA256_PREFIX):
            raise ValueError("signal file hash mismatch: " + digest[:16])
        # signals by the session they may first be traded: the open of the second
        # session after the acceptance date (one complete session must pass)
        self.pending = {}
        rows = [r for r in csv.strip().splitlines()[1:] if r]
        kept = 0
        for r in rows:
            sym, stamp, n, usd = r.split(",")
            if int(n) < self.min_insiders or float(usd) < self.min_combined:
                continue
            accepted = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=4)  # UTC -> ET (approx.)
            key = accepted.date()
            self.pending.setdefault(key, []).append((sym, int(n), float(usd)))
            kept += 1
        self.debug(f"signals kept {kept} on {len(self.pending)} acceptance dates")
        self.open_positions = {}   # symbol -> exit session index
        self.session = 0
        self.queue = []            # (release_session, symbol, usd)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.at(9, 25), self.before_open)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.at(16, 5), self.after_close)

    def after_close(self):
        # acceptances dated today (or a non-session day since the last session) are
        # released two sessions from now
        d = self.time.date()
        for back in range(0, 4):
            day = d - timedelta(days=back)
            for ticker, n, usd in self.pending.pop(day, []):
                # subscribe now, so the security has two sessions of data at
                # the entry open (LEAN cannot price an order on its first bar)
                try:
                    sec = self.add_equity(ticker, Resolution.DAILY)
                except Exception:
                    continue
                self.queue.append((self.session + 2, sec.symbol, usd))
        self.session += 1
        self.log(f"EQ,{d.isoformat()},{self.portfolio.total_portfolio_value:.4f},{self.portfolio.invested}")

    def before_open(self):
        # exits first
        for sym, exit_at in list(self.open_positions.items()):
            if self.session >= exit_at:
                self.market_on_open_order(sym, -self.portfolio[sym].quantity)
                del self.open_positions[sym]
        due = [q for q in self.queue if q[0] <= self.session]
        self.queue = [q for q in self.queue if q[0] > self.session]
        due.sort(key=lambda q: -q[2])
        room = self.max_positions - len(self.open_positions)
        for _, sym, usd in due:
            if room <= 0:
                break
            sec = self.securities[sym]
            if sym in self.open_positions or not sec.has_data or sec.price <= 0:
                continue
            hist = self.history(sym, 21, Resolution.DAILY)
            if hist.empty or len(hist) < 20:
                continue
            closes = hist["close"]; vols = hist["volume"]
            price = float(closes.iloc[-1])
            dollar = float((closes * vols).median())
            if price < 5 or dollar < 5e6:
                continue
            slice_value = self.portfolio.total_portfolio_value / self.max_positions
            qty = int(slice_value // price)
            if qty < 1:
                continue
            self.market_on_open_order(sym, qty)
            self.open_positions[sym] = self.session + self.hold
            room -= 1

    def on_order_event(self, event):
        if event.status == OrderStatus.INVALID:
            self.debug(f"invalid order {event.symbol} {event.message}")
