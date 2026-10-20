"""Agent policy on the IMS algebra: identity pinning, scopes, constraints and revocation."""
from core.agents import AgentPolicy, schema_scope


def make():
    p = AgentPolicy(["search", "ops"], {"pubmed": {"search": {"q"}}, "fs": {"read": {"path"}, "write": {"path"}}})
    p.allow("search", "pubmed", [("search", "ok")])
    p.allow("ops", "fs", [("read", "info"), ("write", "out")])
    p.allow("search", "fs", [("read", "info"), ("write", "out")])
    p.restrict("fs", ("write", "out"), ["ops"], default_deny=False)  # only ops may write
    p.build()
    p.register_agent("a1", "search")
    p.register_agent("a2", "ops")
    p.register_server("s1", "pubmed")
    p.register_server("s2", "fs")
    p.register_server("evil", None)  # declares the name "pubmed" but is not verified
    return p


def test_identity_scope_and_constraint():
    p = make()
    assert p.decide("a1", "s1", "search", "ok")
    assert not p.decide("a1", "evil", "search", "ok")          # same tool name, unverified server
    assert not p.decide("a1", "s1", "search", "extra")         # parameters outside the schema
    assert p.decide("a1", "s2", "read", "info")
    assert not p.decide("a1", "s2", "write", "out")            # removed by the constraint at composition
    assert p.decide("a2", "s2", "write", "out")


def test_revocation_is_one_write():
    p = make()
    p.revoke_agent("a1")
    assert not p.decide("a1", "s1", "search", "ok")


def test_schema_scope():
    schema = {"pubmed": {"search": {"q"}}}
    assert schema_scope("pubmed", "search", {"q"}, schema) == "ok"
    assert schema_scope("pubmed", "search", {"q", "llm_model_name"}, schema) == "extra"
    assert schema_scope("pubmed", "other", {"q"}, schema) == "unknown-tool"
