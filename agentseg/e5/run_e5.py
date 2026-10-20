"""E5: agent tool-call segmentation, offline replay of MCP Security Bench (MSB) and InjecAgent.

No language model runs. Each benchmark case is turned into the tool calls its attack needs if the
agent complies; a policy blocks the case if it denies at least one required step. A step can
have alternatives (for example, a file write can also be done through a granted shell); it is
denied only if every alternative is denied. This measures what each policy can stop at all,
independently of the model and of the wording of the injection.

Policies:
  P0  none: every configured tool may be called.
  P1  per-role allow-list of tool *names* (trust by declaration; the usual framework setting).
  P2  AgentSeg: role intents over *verified* server identities (unverified servers carry the Null
      identity), any parameters.
  P3  AgentSeg: P2 with parameter scope: arguments must fit the verified schema; file tools carry
      a path/operation scope (the retrieval role may read the information folder only).
MSB: required calls are derived from the benchmark's server configuration (main.py,
complete_server_config) and its attack implementations (attack_task.jsonl). Tool names and
parameters of the local servers are read from their source with ast (the code is not run).
InjecAgent: a case needs every listed attacker tool; P1 allows the user tool's toolkit, P2/P3
the task's own tool (a task-scoped intent).
Writes results/e5.json and results/e5_summary.md.
"""
import ast
import collections
import glob
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
from core.agents import AgentPolicy, schema_scope  # noqa: E402

DS = os.path.join(HERE, "..", "datasets")
MSB = os.path.join(DS, "D4_mcp_security_bench")
ATTACK_TOOLS = os.path.join(MSB, "msb_pipeline_github", "data", "tools", "attack_tools")
INJ = os.path.join(DS, "D5_injecagent", "data")
OUT = os.path.join(HERE, "results", "e5.json")
SUMMARY = os.path.join(HERE, "results", "e5_summary.md")

# @modelcontextprotocol/server-filesystem tool list (its README); desktop-commander's kill_process
FS_TOOLS = {"read_text_file", "read_media_file", "read_multiple_files", "write_file", "edit_file", "create_directory",
            "list_directory", "list_directory_with_sizes", "directory_tree", "move_file", "search_files",
            "get_file_info", "list_allowed_directories"}
FS_READ = {"read_text_file", "read_media_file", "read_multiple_files", "list_directory", "list_directory_with_sizes",
           "directory_tree", "search_files", "get_file_info", "list_allowed_directories"}
LOCAL = {"PubMed_MCP_Server": ("academic_search", "pubmed_server"), "DuckDuckGo_Search_Server": ("information_gathering", "server"),
         "Terminal_Controller": ("it_development_management", "terminal_controller"), "Memory_Tool": ("llm_enhancement", "main"),
         "Office_Word_Document_Server": ("office_assistance", "word_mcp_server")}
ATTACK_SERVER_TYPES = {"name_overlap", "preference_manipulation", "out_of_scope_parameter", "tool_transfer",
                       "preference_manipulation-out_of_scope_parameter", "preference_manipulation-simulated_user"}
NO_SUPPORT = {"out_of_scope_parameter", "tool_transfer", "preference_manipulation-out_of_scope_parameter"}
LEAK_BY_PARAM = {"out_of_scope_parameter", "tool_transfer", "preference_manipulation-out_of_scope_parameter"}


def tools_of(path, register=None):
    """Tools declared with @mcp.tool. If the file defines register_tools_<register>() (the Word
    server keeps one registration function per attack type), only that function is read."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    if register:
        fns = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == f"register_tools_{register}"]
        if fns:
            tree = fns[0]
    out = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(
                (isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool") or getattr(d, "attr", "") == "tool"
                for d in n.decorator_list):
            out[n.name] = {a.arg for a in n.args.args} - {"ctx"}
    return out


def variant(server, attack_type):
    agent, base = LOCAL[server]
    suffix = "preference_manipulation" if attack_type == "preference_manipulation-simulated_user" else attack_type
    files = glob.glob(os.path.join(ATTACK_TOOLS, agent, server, f"*-{suffix}.py"))
    return tools_of(files[0], attack_type.replace("-", "_"))


def benign_schema(server):
    """Benign tool names and parameters: the name-overlap variant with the _v1 suffix removed
    (the base file of the Word server registers most tools in other modules)."""
    t = variant(server, "name_overlap")
    return {k[:-3] if k.endswith("_v1") else k: v for k, v in t.items()}


# ------------------------------------------------------------------ MSB
def msb():
    roles = {}
    for line in open(os.path.join(MSB, "hf_data", "agent_task.jsonl"), encoding="utf-8"):
        if line.strip():
            a = json.loads(line)
            roles[a["agent_name"]] = {t["tool"] for t in a["task_tool"]}
    cases = [json.loads(l) for l in open(os.path.join(MSB, "hf_data", "case_manifest.jsonl"), encoding="utf-8")]
    schema = {s: benign_schema(s) for s in LOCAL}
    schema["Filesystem_MCP_Server"] = {t: {"path", "content", "edits", "paths", "source", "destination", "pattern"} for t in FS_TOOLS}
    # identities that are verified: every benign server named in the agents' tasks
    verified = set().union(*roles.values())
    pol2 = AgentPolicy(roles, {s: schema.get(s, {}) for s in verified})
    pol3 = AgentPolicy(roles, {s: schema.get(s, {}) for s in verified})
    for r, srvs in roles.items():
        for s in srvs:
            tools = schema.get(s)
            names = sorted(tools) if tools else ["*"]
            pol2.allow(r, s, [(t, "any") for t in names])
            if s == "Filesystem_MCP_Server":
                rel = [(t, "read:information") for t in sorted(FS_READ)]
            elif s == "Terminal_Controller":
                rel = [(t, "ok") for t in names] + [("execute_command", "shell")]
            else:
                rel = [(t, "ok") for t in names]
            pol3.allow(r, s, rel)
    for p in (pol2, pol3):
        p.build()
        for r in roles:
            p.register_agent(r, r)
        for s in verified:
            p.register_server(s, s)
        for s in ("attack-server", "addition-attack-server", "desktop-commander", "unverified-filesystem"):
            p.register_server(s, None)
    names_p1 = {r: set().union(*((schema.get(s) or {}).keys() for s in srvs)) for r, srvs in roles.items()}

    def call(server_id, identity, tool, params, kind):
        return {"server": server_id, "identity": identity, "tool": tool, "params": params, "kind": kind}

    def support_steps(task, role):
        shell = "Terminal_Controller" in roles[role]
        fs = "Filesystem_MCP_Server" in roles[role]
        fs_id = ("Filesystem_MCP_Server", "Filesystem_MCP_Server") if fs else ("unverified-filesystem", None)

        def fs_call(tool, path):
            alts = [call(fs_id[0], fs_id[1], tool, {"path"}, "write" if tool not in FS_READ else f"read:{path}")]
            if shell:
                alts.append(call("Terminal_Controller", "Terminal_Controller", "execute_command", {"command"}, "shell"))
            return alts
        if task == "kill_process":
            alts = [call("desktop-commander", None, "kill_process", {"pid"}, "process")]
            if shell:
                alts.append(call("Terminal_Controller", "Terminal_Controller", "execute_command", {"command"}, "shell"))
            return [alts]
        if task == "obtain_data_information":
            return [fs_call("read_text_file", "personal"), fs_call("write_file", "output")]
        if task == "modify_data":
            return [fs_call("edit_file", "output")]
        return [fs_call("write_file", "output")]  # remote control (key), agent interaction data

    def steps(c):
        at, role, tool = c["attack_type"], c["agent_name"], c["benign_tool"]
        st = []
        if at in ATTACK_SERVER_TYPES and tool in LOCAL:
            v = variant(tool, at)
            leak = at in LEAK_BY_PARAM and at != "tool_transfer"  # TT: first step is any tool of the transfer server
            base = schema[tool]
            extra = lambda t, p: t in base and not p <= base[t] or t not in base and p - set().union(*base.values())  # noqa: E731
            step = [call("attack-server", None, t, p, "leak" if leak else "attack-tool") for t, p in v.items()
                    if not leak or extra(t, p)]
            if not step:
                raise SystemExit(f"no attack step for {tool} {at}")
            st.append(step)
            if at == "tool_transfer":
                v2 = variant(tool, "out_of_scope_parameter")
                st.append([call("addition-attack-server", None, t, p, "leak") for t, p in v2.items() if extra(t, p)])
        elif at in ATTACK_SERVER_TYPES:
            return None  # MSB itself skips these (no attack server for this benign tool)
        if at not in NO_SUPPORT:
            st += support_steps(c["attack_task"], role)
        return st

    def allowed(policy, role, x):
        if policy == "P0":
            return True
        if policy == "P1":
            return x["tool"] in names_p1[role] or (x["tool"] in FS_TOOLS and "Filesystem_MCP_Server" in roles[role])
        pol = pol2 if policy == "P2" else pol3
        if policy == "P2":
            scope = "any"
        elif x["kind"] == "shell":
            scope = "shell"
        elif x["identity"] == "Filesystem_MCP_Server":
            scope = "read:information" if x["kind"].startswith("read") else "write"
        else:
            scope = schema_scope(x["identity"], x["tool"], x["params"], pol.schema) if x["identity"] else "ok"
        tool = x["tool"] if (x["identity"] in schema or x["identity"] is None or x["identity"] == "Filesystem_MCP_Server") else "*"
        return pol.decide(role, x["server"], tool, scope)

    res = collections.defaultdict(lambda: collections.Counter())
    skipped = 0
    residual = collections.Counter()
    for c in cases:
        st = steps(c)
        if st is None:
            skipped += 1
            continue
        res[c["attack_type"]]["cases"] += 1
        for p in ("P0", "P1", "P2", "P3"):
            blocked = any(not any(allowed(p, c["agent_name"], x) for x in alts) for alts in st)
            res[c["attack_type"]][p] += blocked
            if p == "P3" and not blocked:
                residual[c["agent_name"]] += 1
    # benign: every task's own server must stay reachable
    def probe(s):  # one legitimate call per task server: a read tool for the file server
        if s == "Filesystem_MCP_Server":
            return "read_text_file"
        return sorted(schema[s])[0] if s in schema else "*"
    benign_ok = {p: all(pol.decide(r, s, probe(s), "any" if p == "P2" else
                                   ("read:information" if s == "Filesystem_MCP_Server" else "ok"))
                        for r, srvs in roles.items() for s in srvs)
                 for p, pol in (("P2", pol2), ("P3", pol3))}
    return {"by_type": {k: dict(v) for k, v in res.items()}, "skipped_no_attack_server": skipped,
            "p3_residual_by_role": dict(residual), "benign_task_servers_allowed": benign_ok,
            "roles": {r: sorted(s) for r, s in roles.items()}}, pol3


# ------------------------------------------------------------------ InjecAgent
def injecagent():
    kits = json.load(open(os.path.join(INJ, "tools.json"), encoding="utf-8"))
    kit_tools = {k["toolkit"]: {k["toolkit"] + t["name"] for t in k["tools"]} for k in kits}

    def kit(name):
        for k, ts in kit_tools.items():
            if name in ts:
                return k
        return None

    out, timings = {}, []
    for setting in ("base", "enhanced"):
        for part in ("dh", "ds"):
            cases = json.load(open(os.path.join(INJ, f"test_cases_{part}_{setting}.json"), encoding="utf-8"))
            roles = {f"task{i}": c for i, c in enumerate(cases)}
            pol = AgentPolicy(roles, {k: {} for k in kit_tools})
            for r, c in roles.items():
                pol.allow(r, kit(c["User Tool"]), [(c["User Tool"], "any")])  # task-scoped intent
            pol.build()
            for r in roles:
                pol.register_agent(r, r)
            for k in kit_tools:
                pol.register_server(k, k)
            cnt = collections.Counter()
            for r, c in roles.items():
                cnt["cases"] += 1
                ku = kit(c["User Tool"])
                p1 = any(kit(a) != ku for a in c["Attacker Tools"])
                t0 = time.perf_counter()
                p2 = any(not pol.decide(r, kit(a), a, "any") for a in c["Attacker Tools"])
                timings.append((time.perf_counter() - t0) / len(c["Attacker Tools"]))
                cnt["P1"] += p1
                cnt["P2"] += p2
                cnt["same_tool"] += any(a == c["User Tool"] for a in c["Attacker Tools"])
            out[f"{part}_{setting}"] = dict(cnt)
    return out, timings


def main():
    m, pol3 = msb()
    inj, timings = injecagent()
    # decision cost of the agent group table (Python), many repeats of one MSB decision
    reps = 200_000
    t0 = time.perf_counter()
    for _ in range(reps):
        pol3.decide("academic_search", "PubMed_MCP_Server", "search_pubmed_key_words", "ok")
    per = (time.perf_counter() - t0) / reps
    res = {"msb": m, "injecagent": inj, "python_decision_ns": 1e9 * per,
           "injecagent_decision_ns_median": 1e9 * statistics.median(timings)}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    summarize(res)


def summarize(res):
    L = ["# E5: agent tool-call segmentation (offline replay)", "", "## MSB: attack cases blocked", "",
         "| Attack type | Cases | P0 none | P1 name allow-list | P2 AgentSeg identity | P3 AgentSeg + scope |", "|---|---|---|---|---|---|"]
    tot = collections.Counter()
    for at, c in sorted(res["msb"]["by_type"].items()):
        L.append(f"| {at} | {c['cases']} | " + " | ".join(f"{100 * c.get(p, 0) / c['cases']:.1f}%" for p in ("P0", "P1", "P2", "P3")) + " |")
        tot.update(c)
    L.append(f"| all | {tot['cases']} | " + " | ".join(f"{100 * tot[p] / tot['cases']:.1f}%" for p in ("P0", "P1", "P2", "P3")) + " |")
    L += ["", f"Cases MSB itself skips (no attack server for the benign tool): {res['msb']['skipped_no_attack_server']}.",
          f"Cases not blocked by P3, by role: {res['msb']['p3_residual_by_role']}.",
          f"Benign task servers reachable: {res['msb']['benign_task_servers_allowed']}.", "",
          "## InjecAgent: attack cases blocked", "", "| Set | Cases | P1 toolkit role | P2 task-scoped | Attacker tool = user tool |", "|---|---|---|---|---|"]
    for k, c in res["injecagent"].items():
        L.append(f"| {k} | {c['cases']} | {100 * c['P1'] / c['cases']:.1f}% | {100 * c['P2'] / c['cases']:.1f}% | {c['same_tool']} |")
    L += ["", f"Python decision cost: {res['python_decision_ns']:.0f} ns per call (agent group table)."]
    with open(SUMMARY, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
