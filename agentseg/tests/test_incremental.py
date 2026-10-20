"""Incremental intent addition and EP create/destroy must match full recomputation."""
import random

from core.incremental import add_intents
from ims.compiler import add_ep, compile_intents, remove_ep
from ims.datasets import make_eps
from ims.policy import compose, plain
from test_ims import rules
from test_ims import small_case


def test_incremental_add_equals_full_compose():
    for hashed in (True, False):
        f, valid, I_raw, C_raw, R_raw = small_case(True, 10)
        I, C = compose(I_raw[:30], C_raw, hashed)
        add_intents(I, C, I_raw[30:] + R_raw, hashed)
        full, _ = compose(I_raw + R_raw, C_raw, hashed)
        assert plain(I) == plain(full)


def test_ep_create_destroy_matches_recompile():
    f, valid, I_raw, C_raw, _ = small_case(True, 11)
    I, _ = compose(I_raw, C_raw)
    eps = make_eps(valid, 60, 11)
    ft, groups = compile_intents(I, eps)
    rng, pool = random.Random(2), sorted(valid)
    for a in rng.sample(sorted(eps), 15):
        remove_ep(ft, groups, eps, a)
    for a in range(1000, 1015):
        add_ep(ft, groups, I, eps, a, rng.choice(pool))
    fresh, _ = compile_intents(I, dict(eps))
    assert rules(ft) == rules(fresh) and ft.n_rules == fresh.n_rules
