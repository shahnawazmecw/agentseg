"""E6: AgentDojo (banking suite) with a small local model, with and without AgentSeg.

Model: qwen2.5:1.5b served by Ollama through its OpenAI-compatible endpoint with native tool calling
(AgentDojo's "openai-compatible" provider; its prompt-based "local" provider produced no parsable calls),
CPU only. AgentSeg sits in the tool-execution path: every tool call is checked by an AgentPolicy
(core/agents.py) whose intent for a user task allows the tools of that task. The intents are
taken from the task's reference solution (ground_truth), so they are *oracle* intents: an upper
bound on how precisely an operator could state them. A denied call is not executed; the model
receives an error message instead.

Runs: every user task without attack (utility), and every user task with every injection task
under AgentDojo's "important_instructions" attack (the benchmark's full design). AgentDojo stores one result file per
run and skips runs already done, so the script resumes after a stop.
Usage (from the agentdojo venv): python e6/run_e6.py [--deadline SECONDS]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ.setdefault("OPENAI_COMPATIBLE_BASE_URL", "http://localhost:11434/v1")  # Ollama, native tool calling
os.environ.setdefault("OPENAI_COMPATIBLE_API_KEY", "ollama")

from agentdojo.agent_pipeline import AgentPipeline, PipelineConfig, ToolsExecutionLoop, ToolsExecutor  # noqa: E402
from agentdojo.attacks.attack_registry import load_attack  # noqa: E402
from agentdojo.benchmark import run_task_with_injection_tasks, run_task_without_injection_tasks  # noqa: E402
from agentdojo.functions_runtime import FunctionCall  # noqa: E402
from agentdojo.logging import OutputLogger  # noqa: E402
from agentdojo.task_suite.load_suites import get_suite  # noqa: E402
from agentdojo.types import ChatToolResultMessage, text_content_block_from_string  # noqa: E402

from core.agents import AgentPolicy  # noqa: E402

MODEL = "qwen2.5:1.5b"
SUITE = "banking"
LOGDIR = Path(HERE) / "results" / "e6_runs"
OUT = os.path.join(HERE, "results", "e6.json")


class AgentSegExecutor(ToolsExecutor):
    """Executes only the tool calls the AgentSeg policy allows for the current task."""

    def __init__(self, policy, scope=None):
        super().__init__()
        self.policy = policy
        self.scope = scope or (lambda task, call: "any")
        self.task = None
        self.denied = 0

    def query(self, query, runtime, env, messages, extra_args):
        last = messages[-1]
        calls = last.get("tool_calls") or []
        ok, bad = [], []
        for c in calls:
            (ok if self.policy.decide(self.task, "suite", c.function, self.scope(self.task, c)) else bad).append(c)
        self.denied += len(bad)
        trimmed = dict(last)
        trimmed["tool_calls"] = ok  # the parent executes only the allowed calls (none if empty)
        q, rt, ev, out, ea = super().query(query, runtime, env, [*messages[:-1], trimmed], extra_args)
        out = list(out)
        out[len(messages) - 1] = last  # keep the model's original message in the history
        denials = [ChatToolResultMessage(role="tool", content=[text_content_block_from_string("")], tool_call_id=c.id,
                                         tool_call=c, error=f"Denied by AgentSeg policy: tool {c.function} is not allowed for this task.")
                   for c in bad]
        return q, rt, ev, [*out, *denials], ea


# Parameter scope for the tools that move money or change credentials: the call is in scope only
# if its key argument takes a value the task's intent names (from the reference solution).
KEY_ARG = {"send_money": "recipient", "schedule_transaction": "recipient",
           "update_scheduled_transaction": "recipient", "update_password": "password"}


def build(suite, scoped=False):
    env = suite.load_and_inject_default_environment({})
    tasks = suite.user_tasks
    intents, refs = {}, {}
    for tid, t in tasks.items():
        gt = [c for c in t.ground_truth(env.model_copy(deep=True)) if isinstance(c, FunctionCall)]
        intents[tid] = sorted({c.function for c in gt})
        refs[tid] = {}
        for c in gt:
            if c.function in KEY_ARG:
                refs[tid].setdefault(c.function, set()).add(str(c.args.get(KEY_ARG[c.function])))
    tools = sorted(f.name for f in suite.tools)
    pol = AgentPolicy(list(tasks), {"suite": {t: set() for t in tools}})
    for tid, ts in intents.items():
        pol.allow(tid, "suite", [(t, "ref" if scoped and t in KEY_ARG else "any") for t in ts])
    pol.build()
    for tid in tasks:
        pol.register_agent(tid, tid)
    pol.register_server("suite", "suite")

    def scope(task, call):
        if not scoped or call.function not in KEY_ARG:
            return "any"
        v = call.args.get(KEY_ARG[call.function])
        if v is None and call.function == "update_scheduled_transaction":
            return "ref"  # not changing the recipient
        return "ref" if str(v) in refs[task].get(call.function, ()) else "other"
    return pol, intents, scope


def pipelines(policy, scoped_policy, scope):
    cfg = PipelineConfig(llm="openai-compatible", model_id=MODEL, defense=None, system_message_name=None, system_message=None)
    base = AgentPipeline.from_config(cfg)
    base.name = "openai-compatible-qwen1.5b-none"  # the attack finds the model by this key
    guarded = AgentPipeline.from_config(cfg)
    ex = AgentSegExecutor(policy)
    loop = guarded.elements[-1]
    assert isinstance(loop, ToolsExecutionLoop)
    loop.elements = [ex, *loop.elements[1:]]
    guarded.name = "openai-compatible-qwen1.5b-agentseg"
    scoped = AgentPipeline.from_config(cfg)
    ex2 = AgentSegExecutor(scoped_policy, scope)
    loop2 = scoped.elements[-1]
    loop2.elements = [ex2, *loop2.elements[1:]]
    scoped.name = "openai-compatible-qwen1.5b-agentseg_scope"
    return base, guarded, ex, scoped, ex2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline", type=float, default=480)
    args = ap.parse_args()
    stop_at = time.time() + args.deadline
    suite = get_suite("v1", SUITE)
    policy, intents, _ = build(suite)
    scoped_policy, _, scope = build(suite, scoped=True)
    base, guarded, ex, scoped, ex2 = pipelines(policy, scoped_policy, scope)
    inj_ids = sorted(suite.injection_tasks)
    results = json.load(open(OUT)) if os.path.exists(OUT) else {"runs": {}}
    results["intents"] = intents
    LOGDIR.mkdir(parents=True, exist_ok=True)
    with OutputLogger(str(LOGDIR), live=None):
        run_all(suite, [(base, None), (guarded, ex), (scoped, ex2)], inj_ids, results, stop_at)


def run_all(suite, pipes, inj_ids, results, stop_at):
    """Every user task without attack, and with each of the suite's injection tasks."""
    for tid, task in sorted(suite.user_tasks.items(), key=lambda kv: int(kv[0].split("_")[-1])):
        for pipe, ex in pipes:
            for mode in ["none", *inj_ids]:
                key = f"{pipe.name}|{tid}|{mode}"
                if key in results["runs"]:
                    continue
                if time.time() > stop_at:
                    json.dump(results, open(OUT, "w"), indent=1)
                    print("deadline reached; rerun to resume", flush=True)
                    return
                if ex is not None:
                    ex.task = tid
                before, t0 = (ex.denied if ex else 0), time.time()
                if mode == "none":
                    u, _ = run_task_without_injection_tasks(suite, pipe, task, LOGDIR, False, "v1")
                    rec = {"utility": u, "attack_success": None}
                else:
                    attack = load_attack("important_instructions", suite, pipe)
                    ur, sr = run_task_with_injection_tasks(suite, pipe, task, attack, LOGDIR, False, [mode], "v1")
                    rec = {"utility": ur[(tid, mode)], "attack_success": sr[(tid, mode)], "injection_task": mode}
                rec.update(seconds=time.time() - t0, denied_calls=(ex.denied - before) if ex else 0)
                results["runs"][key] = rec
                json.dump(results, open(OUT, "w"), indent=1)
                print(key, rec, flush=True)
    print("all runs done", flush=True)


if __name__ == "__main__":
    main()
