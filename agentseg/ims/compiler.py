"""IMS intent compilation and EP dynamicity (Ma et al., TDSC 2025, Sec. V-D, V-E2).

EPs are int ids (standing in for IPs); an EP's labels are one e_min. A flow rule is
(src, dst, R) in a default-deny data plane.
"""
from .algebra import KV


class FlowTable:
    """D_F: (src, dst) -> [R];  D_E: ep -> {(src, dst)}  (the two dictionaries of Sec. V-E2)."""

    def __init__(self):
        self.DF = {}
        self.DE = {}
        self.n_rules = 0

    def add(self, src, dst, R):
        key = (src, dst)
        lst = self.DF.get(key)
        if lst is None:
            self.DF[key] = [R]
            self.DE.setdefault(src, set()).add(key)
            self.DE.setdefault(dst, set()).add(key)
        else:
            lst.append(R)
        self.n_rules += 1

    def remove_ep(self, ep):
        removed = 0
        for key in self.DE.pop(ep, ()):
            removed += len(self.DF.pop(key))
            other = key[1] if key[0] == ep else key[0]
            peer = self.DE.get(other)
            if peer is not None:
                peer.discard(key)
        self.n_rules -= removed
        return removed


def group_eps(eps, hashed=True):
    groups = KV(hashed)
    for ep, e in eps.items():
        g = groups.get(e)
        if g is None:
            groups.put(e, [ep])
        else:
            g.append(ep)
    return groups


def compile_intents(I, eps, hashed=True):
    """Algorithm 3: hash matching of each EP group to its unique intent, then of each iE
    e_min to its EP group."""
    groups = group_eps(eps, hashed)
    ft = FlowTable()
    for e, src_eps in groups.items():
        ent = I.get(e)
        if ent is None:
            continue
        for R, s in ent.items():
            for x in s:
                dst_eps = groups.get(x)
                if dst_eps is None:
                    continue
                for a in src_eps:
                    for b in dst_eps:
                        if a != b:
                            ft.add(a, b, R)
    return ft, groups


def update_ep(ft, groups, I, eps, a, new_e):
    """Algorithm 6: relabel EP a. Delete its rules through D_E/D_F, then compile in two
    rounds (a as source, a as destination) instead of recompiling everything."""
    removed = remove_ep(ft, groups, eps, a)
    return removed, add_ep(ft, groups, I, eps, a, new_e)


def remove_ep(ft, groups, eps, a):
    """EP dynamicity type B (destroy): delete the EP's rules through D_E/D_F."""
    removed = ft.remove_ep(a)
    old = groups.get(eps[a])
    old.remove(a)
    if not old:
        groups.pop(eps[a])
    del eps[a]
    return removed


def add_ep(ft, groups, I, eps, a, new_e):
    """EP dynamicity type A (create and label): the two compilation rounds of Algorithm 6."""
    eps[a] = new_e
    g = groups.get(new_e)
    if g is None:
        groups.put(new_e, [a])
    else:
        g.append(a)
    before = ft.n_rules
    ent = I.get(new_e)  # round 1: a -> (Phi_E - a)
    if ent is not None:
        for R, s in ent.items():
            for x in s:
                dst = groups.get(x)
                if dst is None:
                    continue
                for b in dst:
                    if b != a:
                        ft.add(a, b, R)
    for e, src_eps in groups.items():  # round 2: (Phi_E - a) -> a
        ent = I.get(e)
        if ent is None:
            continue
        for R, s in ent.items():
            if new_e in s:
                for b in src_eps:
                    if b != a:
                        ft.add(b, a, R)
    return ft.n_rules - before
