"""IMS label system and EPG space algebra (Ma et al., TDSC 2025, Sec. IV).

An EP carries exactly one value per label type, so an e_min (one value per type) is
encoded as a single int in mixed radix. An EPG is a frozenset of these ints.
"""
from itertools import product


class LabelForest:
    """k label trees with n_values leaves each; value 0 of every tree is Null (Sec. IV-C, step 1)."""

    def __init__(self, n_types=4, n_values=5, valid=None):
        self.k = n_types
        self.n = n_values
        self.radix = [n_values ** i for i in range(n_types)]
        self.valid = valid  # None, or a set of valid e_min ints (optimization A)

    def encode(self, values):
        return sum(v * r for v, r in zip(values, self.radix))

    def decode(self, e):
        return tuple((e // r) % self.n for r in self.radix)

    def all_emins(self):
        return range(self.n ** self.k)

    def epg(self, spec):
        """spec: {label_type: iterable of values}. Unspecified types select all values (Sec. IV-C, step 2)."""
        axes = [sorted(spec[i]) if i in spec else range(self.n) for i in range(self.k)]
        out = (self.encode(vals) for vals in product(*axes))
        if self.valid is not None:
            return frozenset(e for e in out if e in self.valid)
        return frozenset(out)


def restrict_pairwise(forest, a, b, allowed):
    """Optimization A: admin rule 'type a value x may only have type b values allowed[x]'.

    Returns the set of valid e_min. With one allowed value per x, the e_min count drops to 1/n.
    """
    valid = set()
    for e in forest.all_emins():
        v = forest.decode(e)
        if v[b] in allowed[v[a]]:
            valid.add(e)
    return valid


class KV:
    """Key-value table used for every 'find the same e_min / same R' match in IMS.

    hashed=True is optimization B (hash-based matching, O(1) lookup); hashed=False is the
    traversal baseline (O(n) scan). Set operations on EPGs stay hash-based either way, as in
    the paper ("even when optimization B is not used, we still use hash-based set operations").
    """

    __slots__ = ("hashed", "_d", "_l")

    def __init__(self, hashed=True):
        self.hashed = hashed
        self._d = {} if hashed else None
        self._l = None if hashed else []

    def get(self, k):
        if self.hashed:
            return self._d.get(k)
        for kk, v in self._l:
            if kk == k:
                return v
        return None

    def put(self, k, v):
        if self.hashed:
            self._d[k] = v
            return
        for pair in self._l:
            if pair[0] == k:
                pair[1] = v
                return
        self._l.append([k, v])

    def pop(self, k):
        if self.hashed:
            return self._d.pop(k, None)
        for i, (kk, v) in enumerate(self._l):
            if kk == k:
                del self._l[i]
                return v
        return None

    def items(self):
        return list(self._d.items()) if self.hashed else [(k, v) for k, v in self._l]

    def keys(self):
        return list(self._d) if self.hashed else [k for k, _ in self._l]

    def __len__(self):
        return len(self._d) if self.hashed else len(self._l)
