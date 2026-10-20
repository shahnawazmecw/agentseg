"""IMS functionality layer (Ma et al., TDSC 2025, Sec. V-B, V-C, V-E1).

Raw policies, as produced by the DSL or the dataset generator:
  intent / reachability query: (eE, Rs, iE)                with eE, iE EPGs (frozenset of e_min)
  constraint:                  (E, (eCs, e_dd), (iCs, i_dd))  eCs = [(R, iE)], iCs = [(R, eE)]
A relation R is a hashable (protocol, port) tuple.

Processed forms keep one entry per e_min, as the paper does after Definitions 1 and 2:
  intent set:     KV  e_min -> KV R -> set(e_min)            ("(e_e,min, (R, iE))")
  constraint set: KV  e_min -> Con(e: KV R -> set, e_dd, i: KV R -> set, i_dd)
"""
from .algebra import KV


class Con:
    __slots__ = ("e", "e_dd", "i", "i_dd")

    def __init__(self, hashed):
        self.e, self.e_dd = KV(hashed), False
        self.i, self.i_dd = KV(hashed), False


# --- Definition 1: redundancy processing within an intent (or RQ) set -------------------------

def merge_intents(raw, hashed=True, into=None):
    out = into if into is not None else KV(hashed)
    for eE, Rs, iE in raw:
        for e in eE:
            ent = out.get(e)
            if ent is None:
                ent = KV(hashed)
                out.put(e, ent)
            for R in Rs:
                cur = ent.get(R)
                if cur is None:
                    ent.put(R, set(iE))
                else:
                    cur |= iE
    return out


# --- Definition 2: conflict processing within a constraint set --------------------------------

def _merge_side(p, p_dd, q_items, q_dd):
    """Intersect two restriction lists on one direction. A relation listed on one side only is
    kept when the other side does not deny by default; dd of the result is p_dd or q_dd."""
    q_keys = set()
    for R, s in q_items:
        q_keys.add(R)
        cur = p.get(R)
        if cur is not None:
            cur &= s
        elif not p_dd:
            p.put(R, set(s))
    if q_dd:
        for R in p.keys():
            if R not in q_keys:
                p.pop(R)
    return p_dd or q_dd


def merge_constraints(raw, hashed=True, into=None):
    out = into if into is not None else KV(hashed)
    for E, (eCs, e_dd), (iCs, i_dd) in raw:
        for e in E:
            c = out.get(e)
            if c is None:
                c = Con(hashed)
                for R, s in eCs:
                    cur = c.e.get(R)
                    if cur is None:
                        c.e.put(R, set(s))
                    else:
                        cur &= s
                for R, s in iCs:
                    cur = c.i.get(R)
                    if cur is None:
                        c.i.put(R, set(s))
                    else:
                        cur &= s
                c.e_dd, c.i_dd = e_dd, i_dd
                out.put(e, c)
            else:
                c.e_dd = _merge_side(c.e, c.e_dd, eCs, e_dd)
                c.i_dd = _merge_side(c.i, c.i_dd, iCs, i_dd)
    return out


def _ingress_pairs(I, C, hashed):
    """All (constraint subject x, its constraint, egress e_min, R, iE) with x in iE.

    hashed: one pass over the intents, intersecting each iE with the set of constraint subjects
    (a hash set operation that iterates the smaller side, as in IMS Sec. V-F). Otherwise the
    traversal baseline: for every constraint, scan every intent entry."""
    if hashed:
        subjects = set(C.keys())
        for ee, ent in I.items():
            for R, s in ent.items():
                for x in s & subjects:
                    yield x, C.get(x), ee, R, s
    else:
        for x, c in C.items():
            for ee, ent in I.items():
                for R, s in ent.items():
                    if x in s:
                        yield x, c, ee, R, s


# --- Definition 3 / Algorithm 1: constraint-based intent composition --------------------------

def apply_constraints(I, C, hashed=True):
    for e, c in C.items():
        ent = I.get(e)  # egress: intents whose egress e_min is the constraint subject
        if ent is not None:
            for R, s in ent.items():
                lim = c.e.get(R)
                if lim is not None:
                    s &= lim
                elif c.e_dd:
                    ent.pop(R)
    drop = []  # ingress: intents whose iE contains the constraint subject
    for e, c, ee, R, s in _ingress_pairs(I, C, hashed):
        lim = c.i.get(R)
        if (lim is not None and ee not in lim) or (lim is None and c.i_dd):
            drop.append((s, e))
    for s, e in drop:
        s.discard(e)
    return I


def compose(intents_raw, constraints_raw, hashed=True):
    I = merge_intents(intents_raw, hashed)
    C = merge_constraints(constraints_raw, hashed)
    apply_constraints(I, C, hashed)
    return I, C


# --- Definitions 4, 5 / Algorithm 2: policy-level reachability verification -------------------

def verify(I, C, rq_raw, hashed=True, fix=True):
    """Algorithm 2. Returns the number of violated (e_min, R, e_min) reachability triples and
    fixes them if asked."""
    RQ = merge_intents(rq_raw, hashed)
    return verify_constraints(C, RQ, hashed, fix) + verify_intents(I, RQ, hashed, fix)


def verify_constraints(C, RQ, hashed=True, fix=True):
    violated = 0
    for e, c in C.items():  # Definition 4, egress
        q = RQ.get(e)
        if q is None:
            continue
        for R, s in q.items():
            lim = c.e.get(R)
            if lim is not None:
                miss = s - lim
                if miss:
                    violated += len(miss)
                    if fix:
                        lim |= miss
            elif c.e_dd:
                violated += len(s)
                if fix:
                    c.e.put(R, set(s))
    for e, c, qe, R, _ in list(_ingress_pairs(RQ, C, hashed)):  # Definition 4, ingress
        lim = c.i.get(R)
        if lim is not None:
            if qe not in lim:
                violated += 1
                if fix:
                    lim.add(qe)
        elif c.i_dd:
            violated += 1
            if fix:
                c.i.put(R, {qe})
    return violated


def verify_intents(I, RQ, hashed=True, fix=True):
    violated = 0
    for qe, q in RQ.items():  # Definition 5
        ent = I.get(qe)
        if ent is None:
            violated += sum(len(s) for _, s in q.items())
            if fix:
                new = KV(hashed)
                for R, s in q.items():
                    new.put(R, set(s))
                I.put(qe, new)
            continue
        for R, s in q.items():
            cur = ent.get(R)
            if cur is None:
                violated += len(s)
                if fix:
                    ent.put(R, set(s))
            else:
                miss = s - cur
                if miss:
                    violated += len(miss)
                    if fix:
                        cur |= miss
    return violated


# --- Definition 6, Algorithms 4, 5: policy dynamicity -----------------------------------------

def difference(U, V):
    """Definition 6: U - V for processed intent sets, in place on U."""
    for e, v in V.items():
        u = U.get(e)
        if u is None:
            continue
        for R, s in v.items():
            cur = u.get(R)
            if cur is not None:
                cur -= s
    return U


def match_epgs(I, epgs, hashed=True):
    """Intents touching any EP in the EPG set: whole entries whose egress is in it, and the
    parts of other entries whose iE intersects it."""
    sel = set().union(*epgs) if epgs else set()
    M = KV(hashed)
    for e, ent in I.items():
        new = KV(hashed)
        for R, s in ent.items():
            part = set(s) if e in sel else (s & sel)
            if part:
                new.put(R, part)
        if len(new):
            M.put(e, new)
    return M


def delete_intents(I, delete_raw, maintain_epgs, hashed=True):
    """Algorithm 4 with delete given as intents and maintain given as EPGs."""
    D = merge_intents(delete_raw, hashed)
    M = match_epgs(I, maintain_epgs, hashed)
    difference(D, M)
    difference(I, D)
    return I


def add_constraints(I, C, add_raw, hashed=True):
    """Algorithm 5 with maintain = 'original': the new constraints are fixed so that every
    existing intent stays reachable, then merged into C."""
    AC = merge_constraints(add_raw, hashed)
    rq = []
    for e, ent in I.items():
        for R, s in ent.items():
            if s:
                rq.append((frozenset((e,)), (R,), frozenset(s)))
    verify_constraints(AC, merge_intents(rq, hashed), hashed, fix=True)
    merge_constraints(_unprocess(AC), hashed, into=C)
    return C


def clone_intents(I):
    out = KV(I.hashed)
    for e, ent in I.items():
        new = KV(I.hashed)
        for R, s in ent.items():
            new.put(R, set(s))
        out.put(e, new)
    return out


def clone_constraints(C):
    out = KV(C.hashed)
    for e, c in C.items():
        new = Con(C.hashed)
        for R, s in c.e.items():
            new.e.put(R, set(s))
        for R, s in c.i.items():
            new.i.put(R, set(s))
        new.e_dd, new.i_dd = c.e_dd, c.i_dd
        out.put(e, new)
    return out


def plain(I):
    """Processed intent set as plain {e_min: {R: frozenset}}, empty entries dropped (for comparison)."""
    out = {}
    for e, ent in I.items():
        d = {R: frozenset(s) for R, s in ent.items() if s}
        if d:
            out[e] = d
    return out


def _unprocess(C):
    for e, c in C.items():
        yield (frozenset((e,)), (c.e.items(), c.e_dd), (c.i.items(), c.i_dd))
