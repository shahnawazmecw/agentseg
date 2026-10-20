"""Figures for the AgentSeg manuscript, drawn from ../agentseg/results. Writes fig/*.png at 600 dpi,
sized for one IEEE column (3.45 in). Colours: slots 1-3 of the dataviz reference categorical
palette in fixed order; every series also has its own marker and line style for grayscale print."""
import collections
import json
import os
import statistics

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "agentseg", "results")
OUT = os.path.join(HERE, "fig")
C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#222222", "#555555", "#dddddd"
plt.rcParams.update({"font.family": "Times New Roman", "font.size": 8,
                     "mathtext.fontset": "custom", "mathtext.rm": "Times New Roman",  # tick labels such as 10^3
                     "mathtext.it": "Times New Roman:italic", "mathtext.bf": "Times New Roman:bold",
                     "pdf.fonttype": 42, "svg.fonttype": "none", "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.4,
                     "legend.frameon": False, "legend.fontsize": 7})


def jl(name):
    with open(os.path.join(RES, name), encoding="utf-8") as fh:
        return [json.loads(x) for x in fh]


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)


def fig_e1():
    rows = collections.defaultdict(lambda: collections.defaultdict(list))
    info = {}
    for r in jl("e1.jsonl"):
        if r["stage"] == "info":
            info[r["k"]] = r
        elif "seconds" in r:
            rows[r["k"]][r["stage"]].append(r["seconds"])
    ks = sorted(info, key=lambda k: info[k]["microservices"])
    x = [info[k]["microservices"] for k in ks]
    ms = lambda k, s: 1e3 * statistics.mean(rows[k][s])  # noqa: E731
    k0 = next(k for k in ks if rows[k]["pairwise_compile"])
    per_rule = statistics.mean(rows[k0]["pairwise_compile"]) / info[k0]["pairwise_rules"]
    fig, ax = plt.subplots(figsize=(3.45, 2.3))
    ax.plot(x, [ms(k, "compose") for k in ks], color=C1, marker="o", ms=3.5, label="IMS composition")
    ax.plot(x, [ms(k, "verify") for k in ks], color=C2, marker="s", ms=3.5, linestyle="--", label="IMS verification")
    ax.plot(x, [ms(k, "group_compile") for k in ks], color=C3, marker="^", ms=3.5, label="AgentSeg group compilation")
    proj = [1e3 * per_rule * info[k]["pairwise_rules"] for k in ks]
    ax.plot(x, proj, color=INK, linestyle=":", marker="x", ms=3.5, label="IMS per-pair compilation (projected)")
    ax.plot([info[k0]["microservices"]], [ms(k0, "pairwise_compile")], color=INK, marker="D", ms=4, linestyle="none",
            label="IMS per-pair compilation (measured)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Microservices in the policy (Alibaba v2022, window 0)")
    ax.set_ylabel("Time (ms, log scale)")
    style(ax)
    ax.set_ylim(top=3e7)
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.6), fontsize=7)
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(OUT, "e1_scaling.png"), dpi=600)
    fig.savefig(os.path.join(OUT, "e1_scaling.pdf"))
    plt.close(fig)


def fig_drift():
    recs = jl("e2_drift.jsonl")
    Ls = sorted({r["learn_minutes"] for r in recs})
    trip = [statistics.mean(100 * r["denied_triples"] / r["test_triples"] for r in recs if r["learn_minutes"] == L) for L in Ls]
    call = [statistics.mean(100 * r["denied_calls"] / r["test_calls"] for r in recs if r["learn_minutes"] == L) for L in Ls]
    fig, ax = plt.subplots(figsize=(3.45, 2.0))
    ax.plot(Ls, trip, color=C1, marker="o", ms=3.5, label="Distinct call links denied")
    ax.plot(Ls, call, color=C2, marker="s", ms=3.5, linestyle="--", label="Calls denied")
    for L, v in ((Ls[0], trip[0]), (Ls[-1], trip[-1])):
        ax.annotate(f"{v:.1f}%", (L, v), textcoords="offset points", xytext=(4, 3), fontsize=7, color=INK)
    ax.set_xlabel("Learning window (minutes)")
    ax.set_ylabel("Denied in next 15 min (%)")
    ax.set_xticks(Ls)
    style(ax)
    ax.legend(loc="upper right")
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(OUT, "e2_drift.png"), dpi=600)
    fig.savefig(os.path.join(OUT, "e2_drift.pdf"))
    plt.close(fig)


def fig_churn():
    recs = [r for r in jl("e2_churn.jsonl") if r["part"] == "full"]
    ws = sorted({r["window"] for r in recs})
    inc = [1e3 * statistics.mean(r["agentseg_incremental_s"] for r in recs if r["window"] == w) for w in ws]
    full = [1e3 * statistics.mean(r["ims_recompose_s"] for r in recs if r["window"] == w) for w in ws]
    minutes = [3 * w for w in ws]
    fig, ax = plt.subplots(figsize=(3.45, 2.0))
    # same entity colours as Fig. e1: IMS composition = slot 1, AgentSeg = slot 3
    ax.plot(minutes, full, color=C1, marker="o", ms=3.5, linestyle="--", label="IMS full recomposition")
    ax.plot(minutes, inc, color=C3, marker="^", ms=3.5, label="AgentSeg incremental update")
    ax.set_xlabel("Trace minute (start of 3-minute window)")
    ax.set_ylabel("Time per window (ms)")
    ax.set_ylim(bottom=0)
    style(ax)
    ax.legend(loc="center right")
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(OUT, "e2_churn.png"), dpi=600)
    fig.savefig(os.path.join(OUT, "e2_churn.pdf"))
    plt.close(fig)


def fig_arch():
    """Fig. 1: AgentSeg architecture (control plane above, data plane below)."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
    fig, ax = plt.subplots(figsize=(7.0, 2.75))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.axis("off")
    LIGHT1, LIGHT3, GREY = "#cde2fb", "#c8efe0", "#f2f2f0"

    def box(x, y, w, h, text, fc, bold=False, size=7):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", fc=fc, ec=MUTED, lw=0.7))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=INK,
                fontweight="bold" if bold else "normal", linespacing=1.25)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=7, lw=0.8, color=MUTED))

    ax.text(1, 38.2, "Control plane (trusted)", fontsize=7.5, color=INK, fontweight="bold")
    ax.text(1, 15.3, "Data plane (enforcement points, default deny)", fontsize=7.5, color=INK, fontweight="bold")
    ax.plot([0, 100], [16.8, 16.8], color=GRID, lw=0.8, ls="--")
    box(1, 26, 15, 9.5, "Intents\nConstraints\nReachability queries", GREY)
    box(1, 18.6, 40, 5.0, "Orchestrator labels (pods)  ·  capability verifier (agents, servers)", GREY, size=7)
    box(24, 26, 20, 9.5, "IMS algebra\ncompose · verify · fix\n(Defs. 1–6)", LIGHT1, bold=True)
    box(48, 26, 20, 9.5, "Incremental\ncomposition\n(Lemma 2)", LIGHT3, bold=True)
    box(72, 26, 26, 9.5, "Group compiler\nT: (group, R) → groups\nM: endpoint → group", LIGHT3, bold=True)
    arrow(16.6, 30.75, 23.4, 30.75)
    arrow(44.6, 30.75, 47.4, 30.75)
    arrow(68.6, 30.75, 71.4, 30.75)
    arrow(41.6, 21.1, 79, 25.3)
    ax.text(47, 20.0, "labels → M (one write per event)", fontsize=7, color=MUTED, ha="left")
    box(3, 8.6, 36, 5.2, "Pod → pod flow  (src, dst, RPC type)", GREY, size=7)
    box(3, 1.2, 36, 5.6, "Agent → tool call  (agent, server, tool, args);  scope(args) → R", GREY, size=7)
    box(52, 3, 30, 9.5, "Decision\nM[dst] in T[M[src]][R]\n≈ 12 ns per call (Rust)", LIGHT1, bold=True)
    box(87, 3, 11, 9.5, "allow /\ndeny", GREY, bold=True)
    arrow(39.6, 11.2, 51.4, 9.2)
    arrow(39.6, 4.0, 51.4, 6.3)
    arrow(82.6, 7.75, 86.4, 7.75)
    arrow(86, 25.4, 72, 13.1)
    ax.text(80.5, 18.6, "T, M", fontsize=7, color=MUTED)
    fig.tight_layout(pad=0.2)
    fig.savefig(os.path.join(OUT, "arch.png"), dpi=600)
    fig.savefig(os.path.join(OUT, "arch.pdf"))
    plt.close(fig)


def fig_e7():
    with open(os.path.join(RES, "e7_rust.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    th = [s["threads"] for s in d["scaling"]]
    rate = [s["decisions_per_s"] / 1e6 for s in d["scaling"]]
    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    ax.plot(th, rate, color=C3, marker="^", ms=3.5, label="AgentSeg group table (Rust)")
    ax.plot(th, [rate[0] * t for t in th], color=MUTED, ls=":", lw=1, label="Linear from 1 thread")
    ax.axvline(6, color=GRID, lw=0.8)
    ax.text(6.15, max(rate) * 0.45, "6 physical cores", fontsize=7, color=MUTED)
    ax.set_xlabel("Threads")
    ax.set_ylabel("Decisions/s (millions)")
    ax.set_xticks(th)
    ax.set_ylim(0, max(rate) * 1.5)
    style(ax)
    ax.legend(loc="lower right")
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(OUT, "e7_scaling.png"), dpi=600)
    fig.savefig(os.path.join(OUT, "e7_scaling.pdf"))
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_arch()
    fig_e7()
    fig_e1()
    fig_drift()
    fig_churn()
    print("figures written to", OUT)
