"""AgentSeg for AI agents: agents and tool servers as endpoints of the IMS algebra.

Label forest with three types:
  kind      Null | agent | server
  role      Null | one value per agent role
  identity  Null | one value per *verified* server (identity pinned at registration, e.g. a hash
            of the server's package and configuration). A server that is not verified carries
            Null, which no intent selects, whatever name it declares.
An agent endpoint is (agent, its role, Null); a server endpoint is (server, Null, its identity).
A relation R is (tool name, parameter scope). The scope is computed from the call by a
classifier: whether the arguments fit the verified schema, and for file and send tools the
class of path or recipient. Intents say which (tool, scope) a role may use on which verified
server; the processed intent set compiles to a GroupTable, so a decision is two membership
lookups and one set lookup, as for pods.
"""
from ims.algebra import LabelForest
from ims.policy import compose

from .groups import GroupTable

AGENT, SERVER = 1, 2


class AgentPolicy:
    def __init__(self, roles, servers):
        """roles: iterable of role names; servers: {verified server identity: {tool: set(params)}}."""
        self.roles = {r: i + 1 for i, r in enumerate(sorted(roles))}
        self.servers = {s: i + 1 for i, s in enumerate(sorted(servers))}
        self.schema = servers
        n = max(len(self.roles), len(self.servers)) + 1
        self.forest = LabelForest(3, max(n, 3))
        self.intents = []
        self.constraints = []
        self.table = None
        self.members = {}

    def agent_group(self, role):
        return self.forest.epg({0: [AGENT], 1: [self.roles[role]], 2: [0]})

    def server_group(self, identity):
        return self.forest.epg({0: [SERVER], 1: [0], 2: [self.servers[identity]]})

    def allow(self, role, identity, relations):
        """Intent: agents of `role` may use these (tool, scope) relations on verified server `identity`."""
        self.intents.append((self.agent_group(role), tuple(relations), self.server_group(identity)))

    def restrict(self, identity, relation, roles, default_deny=False):
        """Constraint: on `identity`, `relation` is accepted only from the given roles."""
        callers = frozenset().union(*(self.agent_group(r) for r in roles)) if roles else frozenset()
        self.constraints.append((self.server_group(identity), ([], False), ([(relation, callers)], default_deny)))

    def build(self):
        I, _ = compose(self.intents, self.constraints)
        self.table = GroupTable(I, {})
        return I

    def register_agent(self, agent_id, role):
        e = self.forest.encode((AGENT, self.roles.get(role, 0), 0))
        self.table.relabel(("agent", agent_id), e)

    def register_server(self, server_id, identity):
        """identity None (not verified) gives the Null identity value."""
        e = self.forest.encode((SERVER, 0, self.servers.get(identity, 0) if identity else 0))
        self.table.relabel(("server", server_id), e)

    def revoke_agent(self, agent_id):
        self.table.relabel(("agent", agent_id), self.forest.encode((AGENT, 0, 0)))

    def decide(self, agent_id, server_id, tool, scope):
        return self.table.allow(("agent", agent_id), ("server", server_id), (tool, scope))


def schema_scope(identity, tool, params, schema):
    """'ok' if the call's parameters are a subset of the verified schema of that tool, else 'extra'."""
    allowed = schema.get(identity, {}).get(tool)
    if allowed is None:
        return "unknown-tool"
    return "ok" if set(params) <= allowed else "extra"
