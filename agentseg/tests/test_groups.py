"""Group-level compilation must make exactly the decisions IMS's per-pair flow rules make."""
import random

from core.groups import GroupTable
from ims.compiler import compile_intents
from ims.datasets import RELATIONS, make_eps
from test_ims import small_case
from ims.policy import compose


def test_group_table_matches_pairwise_rules():
    f, valid, I_raw, C_raw, _ = small_case(True, 8)
    I, _ = compose(I_raw, C_raw)
    eps = make_eps(valid, 60, 8)
    ft, _ = compile_intents(I, eps)
    pairwise = {(s, d, R) for (s, d), Rs in ft.DF.items() for R in Rs}
    gt = GroupTable(I, eps)
    for s in eps:
        for d in eps:
            if s == d:
                continue
            for R in RELATIONS:
                assert gt.allow(s, d, R) == ((s, d, R) in pairwise)


def test_relabel_matches_recompile():
    f, valid, I_raw, C_raw, _ = small_case(True, 9)
    I, _ = compose(I_raw, C_raw)
    eps = make_eps(valid, 60, 9)
    gt = GroupTable(I, eps)
    rng, pool = random.Random(1), sorted(valid)
    for ep in rng.sample(sorted(eps), 20):
        eps[ep] = rng.choice(pool)
        gt.relabel(ep, eps[ep])
    fresh = GroupTable(I, eps)
    for s in eps:
        for d in eps:
            for R in RELATIONS:
                assert gt.allow(s, d, R) == fresh.allow(s, d, R)
