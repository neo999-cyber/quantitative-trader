from AlgorithmImports import *
import os

class ProbeProjectFiles(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2024, 3, 1)
        self.set_end_date(2024, 3, 8)
        self.set_cash(1000)
        self.debug("cwd " + os.getcwd())
        self.debug("files " + str(sorted(os.listdir("."))[:40]))
        try:
            with open("signals.csv") as f:
                rows = f.read().splitlines()
            self.debug("signals.csv rows " + str(len(rows)) + " first " + rows[1])
        except Exception as e:
            self.debug("open failed: " + repr(e))
        self.add_equity("SPY", Resolution.MINUTE)

    def on_data(self, data):
        pass
