"""Random datasets following IMS Sec. VI: a label forest of 4 trees x 5 leaves, DS1 (2000 intents,
2000 constraints, 2000 RQs), DS2 (1000 intents, 1000 constraints, 1000 EPGs) and 1000 EPs.

The paper does not give the generator's distributions. Ours are calibrated to its reported outputs
(about 10^6 flow rules for 1000 EPs, about 6000 rules per relabelled EP); they are
recorded in the results so the runs can be repeated.
"""
import random

from .algebra import LabelForest, restrict_pairwise

PROTOCOLS = ("TCP", "UDP")
PORTS = (22, 53, 80, 443, 3306, 5432, 6379, 8080, 9092, 27017)
RELATIONS = tuple((p, port) for p in PROTOCOLS for port in PORTS)

GENERATOR = {
    "label_types": 4, "values_per_type": 5,
    "epg_types_specified": (1, 3), "epg_values_per_type": (1, 3),
    "relations": len(RELATIONS), "intent_relations": (1, 3),
    "constraint_subject_types_specified": (4, 4), "constraint_subject_values_per_type": (1, 1),
    "constraint_items_per_side": (1, 2), "default_deny_prob": 0.5,
    "opt_A_rule": "type 0 value x may only have one type-1 value (keeps 1/5 of e_min)",
}


def make_forest(opt_a, seed=0):
    f = LabelForest(GENERATOR["label_types"], GENERATOR["values_per_type"])
    rng = random.Random(seed)
    allowed = {x: {rng.randrange(f.n)} for x in range(f.n)}
    valid = restrict_pairwise(f, 0, 1, allowed)
    if opt_a:
        f.valid = valid
    return f, valid


class Generator:
    def __init__(self, forest, seed=1):
        self.f = forest
        self.rng = random.Random(seed)

    def epg_spec(self, types_key="epg_types_specified", values_key="epg_values_per_type"):
        r, f = self.rng, self.f
        types = r.sample(range(f.k), r.randint(*GENERATOR[types_key]))
        return {t: r.sample(range(f.n), r.randint(*GENERATOR[values_key])) for t in types}

    def relations(self, lo_hi):
        return tuple(self.rng.sample(RELATIONS, self.rng.randint(*lo_hi)))

    def intent_spec(self):
        return (self.epg_spec(), self.relations(GENERATOR["intent_relations"]), self.epg_spec())

    def side_spec(self):
        items = [(self.relations((1, 1))[0], self.epg_spec())
                 for _ in range(self.rng.randint(*GENERATOR["constraint_items_per_side"]))]
        return items, self.rng.random() < GENERATOR["default_deny_prob"]

    def constraint_spec(self):
        subject = self.epg_spec("constraint_subject_types_specified", "constraint_subject_values_per_type")
        return (subject, self.side_spec(), self.side_spec())


def make_specs(seed=1):
    """Label-level specs (independent of optimization A), so both settings see the same policies."""
    f = LabelForest(GENERATOR["label_types"], GENERATOR["values_per_type"])
    g1, g2 = Generator(f, seed), Generator(f, seed + 1)
    ds1 = {"intents": [g1.intent_spec() for _ in range(2000)],
           "constraints": [g1.constraint_spec() for _ in range(2000)],
           "rqs": [g1.intent_spec() for _ in range(2000)]}
    ds2 = {"intents": [g2.intent_spec() for _ in range(1000)],
           "constraints": [g2.constraint_spec() for _ in range(1000)],
           "epgs": [g2.epg_spec() for _ in range(1000)]}
    return ds1, ds2


def realize_intents(f, specs):
    return [(f.epg(a), R, f.epg(b)) for a, R, b in specs]


def realize_constraints(f, specs):
    return [(f.epg(E), ([(R, f.epg(s)) for R, s in eC], edd), ([(R, f.epg(s)) for R, s in iC], idd))
            for E, (eC, edd), (iC, idd) in specs]


def make_eps(valid, n=1000, seed=2):
    """n EPs, each tagged with a random valid label combination (one e_min)."""
    rng = random.Random(seed)
    pool = sorted(valid)
    return {ep: rng.choice(pool) for ep in range(n)}
