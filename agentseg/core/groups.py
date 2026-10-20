"""AgentSeg group-level compilation.

IMS compiles each processed intent into one flow rule per (source EP, destination EP) pair, so
rule count grows with the product of group sizes. Here the processed intent set is kept at
group level, (source e_min, R) -> set of destination e_min, and each endpoint carries only its
group in a membership table. A decision is two membership lookups and one set lookup;
relabelling an endpoint is one table write.
"""


class GroupTable:
    __slots__ = ("rules", "member", "n_rules")

    def __init__(self, I, eps):
        """I: processed IMS intent set (KV e_min -> KV R -> set). eps: {endpoint: e_min}."""
        self.rules = {}
        n = 0
        for e, ent in I.items():
            row = {R: frozenset(s) for R, s in ent.items() if s}
            if row:
                self.rules[e] = row
                n += sum(len(s) for s in row.values())
        self.n_rules = n
        self.member = dict(eps)

    def allow(self, src, dst, R):
        es, ed = self.member.get(src), self.member.get(dst)
        if es is None or ed is None:
            return False
        row = self.rules.get(es)
        return row is not None and ed in row.get(R, ())

    def refresh(self, I, keys):
        """Rebuild the rows of the given source e_min after the processed intent set changed."""
        for e in keys:
            old = self.rules.pop(e, None)
            if old is not None:
                self.n_rules -= sum(len(s) for s in old.values())
            ent = I.get(e)
            if ent is None:
                continue
            row = {R: frozenset(s) for R, s in ent.items() if s}
            if row:
                self.rules[e] = row
                self.n_rules += sum(len(s) for s in row.values())

    def relabel(self, ep, e):
        self.member[ep] = e

    def remove(self, ep):
        self.member.pop(ep, None)
