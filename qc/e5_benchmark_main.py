# E5 benchmark and control (docs/prereg/p2_insider_cluster_v1.md).
# MODE "benchmark": equal weight of the eligible universe (US stocks, price > $5,
#   20-session median dollar volume > $5M), top 500 by dollar volume as the
#   tradeable proxy, rebalanced monthly, fully invested; the exposure-matched
#   comparator is this series scaled to the family's mean exposure locally.
# MODE "random": the family's book with each signal's name replaced by a random
#   eligible name on the same day (gate 6's random-entry null, one draw per run).
from AlgorithmImports import *
from datetime import datetime, timedelta
import base64, hashlib, random, zlib

SIGNALS_URL = "https://raw.githubusercontent.com/neo999-cyber/quantitative-trader/claude/funny-faraday-nizzck/qc/e5_signals.b64"


class E5BenchmarkControl(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2010, 1, 4)
        self.set_end_date(2025, 8, 29)
        self.mode = self.get_parameter("mode", "benchmark")
        self.seed = int(self.get_parameter("seed", "1"))
        self.set_cash(int(self.get_parameter("equity", "100000")))
        self.hold = int(self.get_parameter("hold_sessions", "20"))
        self.max_positions = int(self.get_parameter("max_positions", "4"))
        self.set_security_initializer(lambda s: s.set_fee_model(ConstantFeeModel(0)))
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self.select_coarse)
        self.eligible = []
        self.rng = random.Random(self.seed)
        self.session = 0
        self.open_positions = {}
        self.queue = []
        self.last_rebalance_month = None
        if self.mode == "random":
            raw = self.download(SIGNALS_URL)
            csv = zlib.decompress(base64.b64decode(raw)).decode()
            self.pending = {}
            for r in csv.strip().splitlines()[1:]:
                sym, stamp, n, usd = r.split(",")
                if int(n) < 2 or float(usd) < 100000:
                    continue
                accepted = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=4)
                self.pending.setdefault(accepted.date(), []).append(float(usd))
        self.schedule.on(self.date_rules.every_day(), self.time_rules.at(9, 25), self.before_open)
        self.schedule.on(self.date_rules.every_day(), self.time_rules.at(16, 5), self.after_close)

    def select_coarse(self, coarse):
        ok = [c for c in coarse if c.has_fundamental_data and c.price > 5 and c.dollar_volume > 5e6]
        ok.sort(key=lambda c: -c.dollar_volume)
        self.eligible = [c.symbol for c in ok[:500]]
        return self.eligible

    def after_close(self):
        d = self.time.date()
        if self.mode == "random":
            for back in range(0, 4):
                for usd in self.pending.pop(d - timedelta(days=back), []):
                    self.queue.append((self.session + 2, usd))
        self.session += 1

    def before_open(self):
        if self.mode == "benchmark":
            if self.time.month != self.last_rebalance_month and self.eligible:
                self.last_rebalance_month = self.time.month
                names = [s for s in self.eligible if s in self.securities and self.securities[s].has_data]
                if names:
                    w = 1.0 / len(names)
                    self.set_holdings([PortfolioTarget(s, w) for s in names], liquidate_existing_holdings=True)
            return
        for sym, exit_at in list(self.open_positions.items()):
            if self.session >= exit_at:
                self.market_on_open_order(sym, -self.portfolio[sym].quantity)
                del self.open_positions[sym]
        due = [q for q in self.queue if q[0] <= self.session]
        self.queue = [q for q in self.queue if q[0] > self.session]
        room = self.max_positions - len(self.open_positions)
        pool = [s for s in self.eligible if s in self.securities and self.securities[s].has_data and self.securities[s].price > 5 and s not in self.open_positions]
        for _, usd in due:
            if room <= 0 or not pool:
                break
            sym = self.rng.choice(pool)
            pool.remove(sym)
            price = float(self.securities[sym].price)
            qty = int((self.portfolio.total_portfolio_value / self.max_positions) // price)
            if qty < 1:
                continue
            self.market_on_open_order(sym, qty)
            self.open_positions[sym] = self.session + self.hold
            room -= 1
