"""AgentSeg incremental intent addition.

IMS handles intent addition by re-running constraint-based composition over all intents
(Sec. V-E1). Composition is a per-triple filter: a triple (egress e_min, R, ingress e_min)
survives Definition 3 iff the egress constraint of its source and the ingress constraint of
its destination allow it, independently of every other triple. New triples can therefore be
filtered on their own and merged into the processed set, with the same result as a full
recomposition, at a cost proportional to the new triples rather than to all intents.
"""
from ims.algebra import KV


def add_intents(I, C, new_raw, hashed=True):
    """Merge raw intents (eE, Rs, iE) into the processed intent set I under constraint set C.
    Returns the number of triples that survived the constraints."""
    subjects = set(C.keys())
    kept = 0
    for eE, Rs, iE in new_raw:
        for e in eE:
            ce = C.get(e)
            ent = I.get(e)
            for R in Rs:
                part = set(iE)
                if ce is not None:
                    lim = ce.e.get(R)
                    if lim is not None:
                        part &= lim
                    elif ce.e_dd:
                        continue
                for x in part & subjects:
                    c = C.get(x)
                    lim = c.i.get(R)
                    if (lim is not None and e not in lim) or (lim is None and c.i_dd):
                        part.discard(x)
                if not part:
                    continue
                if ent is None:
                    ent = KV(hashed)
                    I.put(e, ent)
                cur = ent.get(R)
                if cur is None:
                    ent.put(R, part)
                    kept += len(part)
                else:
                    kept += len(part - cur)
                    cur |= part
    return kept
