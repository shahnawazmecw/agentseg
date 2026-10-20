"""Checks of the IMS re-implementation: the paper's worked examples, and invariants that must hold
whichever optimizations are switched on."""
import random

import pytest

from ims.algebra import LabelForest
from ims.compiler import compile_intents, update_ep
from ims.datasets import (Generator, make_eps, make_forest, realize_constraints,
                          realize_intents)
from ims.policy import (add_constraints, apply_constraints, compose, delete_intents,
                        merge_intents, plain, verify)

TCP3306 = ("TCP", 3306)


def test_epg_intersection_example_sec_iv_c():
    f = LabelForest(3, 2)
    Ea, Eb = f.epg({0: [0], 1: [0]}), f.epg({1: [0], 2: [0]})
    assert Ea == {f.encode((0, 0, 0)), f.encode((0, 0, 1))}
    assert Eb == {f.encode((0, 0, 0)), f.encode((1, 0, 0))}
    assert Ea & Eb == {f.encode((0, 0, 0))}


@pytest.mark.parametrize("hashed", [True, False])
def test_fig5_compose_and_verify(hashed):
    # Function {Null, Web, DB} x Application {Null, App1, App2}
    f = LabelForest(2, 3)
    WEB, DB, APP1, APP2 = 1, 2, 1, 2
    web_12, db_12 = f.epg({0: [WEB], 1: [APP1, APP2]}), f.epg({0: [DB], 1: [APP1, APP2]})
    db_1, web_1 = f.epg({0: [DB], 1: [APP1]}), f.epg({0: [WEB], 1: [APP1]})
    intents = [(web_12, (TCP3306,), db_12)]
    constraints = [(db_1, ([], False), ([(TCP3306, web_1)], False))]  # DB in App1 accepts 3306 only from Web in App1
    I, C = compose(intents, constraints, hashed)
    p = plain(I)
    w1, w2 = f.encode((WEB, APP1)), f.encode((WEB, APP2))
    d1, d2 = f.encode((DB, APP1)), f.encode((DB, APP2))
    assert p[w1][TCP3306] == {d1, d2}
    assert p[w2][TCP3306] == {d2}  # Web in App2 may no longer reach DB in App1
    rq = [(f.epg({0: [WEB], 1: [APP2]}), (TCP3306,), f.epg({0: [DB], 1: [APP2]}))]
    assert verify(I, C, rq, hashed, fix=False) == 0


def small_case(opt_a, seed):
    f, valid = make_forest(opt_a)
    g = Generator(LabelForest(4, 5), seed)
    I_raw = realize_intents(f, [g.intent_spec() for _ in range(60)])
    C_raw = realize_constraints(f, [g.constraint_spec() for _ in range(60)])
    R_raw = realize_intents(f, [g.intent_spec() for _ in range(60)])
    return f, valid, I_raw, C_raw, R_raw


def rules(ft):
    return {(s, d, R) for (s, d), Rs in ft.DF.items() for R in Rs}


@pytest.mark.parametrize("seed", [3, 4])
def test_optimizations_do_not_change_results(seed):
    out = {}
    for opt_a in (False, True):
        for hashed in (False, True):
            f, valid, I_raw, C_raw, R_raw = small_case(opt_a, seed)
            I, C = compose(I_raw, C_raw, hashed)
            v = verify(I, C, R_raw, hashed)
            eps = make_eps(valid, 80, seed)
            ft, _ = compile_intents(I, eps, hashed)
            out[(opt_a, hashed)] = (v if not opt_a else None, rules(ft))
    base = out[(False, True)]
    assert out[(False, False)] == base  # B on/off: identical violations and flow rules
    assert out[(True, False)][1] == out[(True, True)][1] == base[1]  # A changes e_min counts, not the rules for valid EPs


@pytest.mark.parametrize("hashed", [True, False])
def test_ep_update_matches_full_recompile(hashed):
    f, valid, I_raw, C_raw, _ = small_case(True, 5)
    I, _ = compose(I_raw, C_raw, hashed)
    eps = make_eps(valid, 80, 5)
    ft, groups = compile_intents(I, eps, hashed)
    rng, pool = random.Random(0), sorted(valid)
    for a in rng.sample(sorted(eps), 15):
        update_ep(ft, groups, I, eps, a, rng.choice(pool))
    fresh, _ = compile_intents(I, dict(eps), hashed)
    assert rules(ft) == rules(fresh)
    assert ft.n_rules == fresh.n_rules


def test_constraint_addition_keeps_original_reachability():
    f, valid, I_raw, C_raw, _ = small_case(True, 6)
    I, C = compose(I_raw, C_raw)
    before = plain(I)
    g = Generator(LabelForest(4, 5), 99)
    add_constraints(I, C, realize_constraints(f, [g.constraint_spec() for _ in range(40)]))
    I2 = merge_intents([(frozenset((e,)), (R,), s) for e, d in before.items() for R, s in d.items()])
    apply_constraints(I2, C)
    assert plain(I2) == before


def test_intent_deletion_keeps_maintained_epgs():
    f, valid, I_raw, C_raw, _ = small_case(True, 7)
    I, _ = compose(I_raw, C_raw)
    before = plain(I)
    g = Generator(LabelForest(4, 5), 77)
    keep = [f.epg(g.epg_spec())]
    delete_intents(I, realize_intents(f, [g.intent_spec() for _ in range(40)]), keep)
    after, sel = plain(I), set().union(*keep)
    for e, d in before.items():
        for R, s in d.items():
            kept = s if e in sel else (s & sel)
            assert kept <= after.get(e, {}).get(R, frozenset())
