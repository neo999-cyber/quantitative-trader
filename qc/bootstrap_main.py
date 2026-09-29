# Bootstrap: fetch the family's implementation from the repo and bind it.
# The family is chosen by the "impl" parameter (default below); change one line to switch.
from AlgorithmImports import *
import types

REPO = "https://raw.githubusercontent.com/neo999-cyber/quantitative-trader/claude/funny-faraday-nizzck/qc/"


class Bootstrap(QCAlgorithm):
    def initialize(self):
        impl = self.get_parameter("impl", "e4_impl.py")
        src = self.download(REPO + impl)
        ns = dict(globals())
        before = set(ns)
        exec(compile(src, impl, "exec"), ns)
        for name in set(ns) - before:
            if isinstance(ns[name], types.FunctionType):
                setattr(self, name, types.MethodType(ns[name], self))
        self.debug("bound " + impl)
        self.impl_initialize()
