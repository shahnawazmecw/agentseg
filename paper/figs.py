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
    """Fig. 1: AgentSeg architecture with drawn icons. Control plane above, data plane below;
    numbered markers follow the flow described in the caption."""
    from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Polygon, Rectangle, RegularPolygon
    fig, ax = plt.subplots(figsize=(7.16, 3.55))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 50)
    ax.set_aspect("equal")
    ax.axis("off")
    T1, T3, T2, TG = "#e8f1fc", "#e2f5ee", "#fdeee6", "#f4f4f2"   # light tints of slots 1, 3, 2 and grey
    D1, D3, D2 = "#1c5cab", "#127a55", "#b8471d"                  # darker steps for icon strokes
    RED, GREEN = "#d23b3a", "#16894f"

    def card(x, y, w, h, fc, ec, lw=0.9, r=1.4):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=1))

    def text(x, y, s, size=7.5, bold=False, color=INK, ha="center", va="center", italic=False, z=6):
        ax.text(x, y, s, fontsize=size, fontweight="bold" if bold else "normal", color=color, ha=ha, va=va,
                style="italic" if italic else "normal", zorder=z, linespacing=1.2)

    def arrow(x1, y1, x2, y2, color=MUTED, lw=1.0, ls="-", conn="arc3,rad=0"):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=8, lw=lw, color=color,
                                     linestyle=ls, connectionstyle=conn, zorder=4, shrinkA=0, shrinkB=0))

    def step(x, y, n, color):
        ax.add_patch(Circle((x, y), 1.35, fc=color, ec="white", lw=0.8, zorder=7))
        text(x, y - 0.05, str(n), size=6.8, bold=True, color="white", z=8)

    # ---- icons, drawn with patches so the figure needs no external icon set
    def ico_doc(x, y, s=1.0, c=D2):
        w, h, f = 3.4 * s, 4.2 * s, 1.1 * s
        ax.add_patch(Polygon([(x, y), (x + w, y), (x + w, y + h - f), (x + w - f, y + h), (x, y + h)], closed=True,
                             fc="white", ec=c, lw=0.9, zorder=5))
        ax.add_patch(Polygon([(x + w - f, y + h), (x + w - f, y + h - f), (x + w, y + h - f)], closed=True, fc=c, ec=c,
                             lw=0.6, zorder=5))
        for k in range(3):
            yy = y + h * (0.62 - 0.2 * k)
            ax.plot([x + 0.6 * s, x + w - 0.7 * s], [yy, yy], color=c, lw=0.8, zorder=6, solid_capstyle="round")

    def ico_pod(x, y, s=1.0, c=D1):
        ax.add_patch(RegularPolygon((x, y), 6, radius=2.0 * s, orientation=0.5236, fc="white", ec=c, lw=0.9, zorder=5))
        ax.add_patch(RegularPolygon((x, y), 4, radius=0.95 * s, orientation=0.7854, fc=c, ec=c, lw=0.5, zorder=6))

    def ico_robot(x, y, s=1.0, c=D3):
        ax.add_patch(FancyBboxPatch((x - 2.0 * s, y - 1.6 * s), 4.0 * s, 3.2 * s,
                                    boxstyle=f"round,pad=0,rounding_size={0.8 * s}", fc="white", ec=c, lw=0.9, zorder=5))
        for dx in (-0.85, 0.85):
            ax.add_patch(Circle((x + dx * s, y + 0.25 * s), 0.42 * s, fc=c, ec=c, zorder=6))
        ax.plot([x - 0.9 * s, x + 0.9 * s], [y - 0.8 * s, y - 0.8 * s], color=c, lw=0.9, zorder=6, solid_capstyle="round")
        ax.plot([x, x], [y + 1.6 * s, y + 2.4 * s], color=c, lw=0.9, zorder=6)
        ax.add_patch(Circle((x, y + 2.6 * s), 0.35 * s, fc=c, ec=c, zorder=6))

    def ico_server(x, y, s=1.0, c=D2):
        for k in range(3):
            yy = y + k * 1.35 * s
            ax.add_patch(FancyBboxPatch((x, yy), 4.2 * s, 1.05 * s, boxstyle=f"round,pad=0,rounding_size={0.25 * s}",
                                        fc="white", ec=c, lw=0.85, zorder=5))
            ax.add_patch(Circle((x + 0.6 * s, yy + 0.52 * s), 0.2 * s, fc=c, ec=c, zorder=6))
            ax.plot([x + 1.5 * s, x + 3.6 * s], [yy + 0.52 * s] * 2, color=c, lw=0.7, zorder=6)

    def ico_badge(x, y, s=1.0, c=D3):
        ax.add_patch(RegularPolygon((x, y), 8, radius=2.0 * s, fc="white", ec=c, lw=0.9, zorder=5))
        ax.plot([x - 0.9 * s, x - 0.2 * s, x + 1.0 * s], [y, y - 0.75 * s, y + 0.8 * s], color=c, lw=1.2, zorder=6,
                solid_capstyle="round", solid_joinstyle="round")

    def ico_shield(x, y, s=1.0, c=D1):
        pts = [(x, y + 2.6 * s), (x + 2.2 * s, y + 1.9 * s), (x + 2.0 * s, y - 0.4 * s), (x, y - 2.3 * s),
               (x - 2.0 * s, y - 0.4 * s), (x - 2.2 * s, y + 1.9 * s)]
        ax.add_patch(Polygon(pts, closed=True, fc=c, ec=c, lw=0.8, zorder=5))
        ax.add_patch(Rectangle((x - 0.85 * s, y - 0.9 * s), 1.7 * s, 1.35 * s, fc="white", ec="white", zorder=6))
        ax.add_patch(FancyBboxPatch((x - 0.55 * s, y + 0.45 * s), 1.1 * s, 1.05 * s, boxstyle="round,pad=0,rounding_size=0.5",
                                    fc="none", ec="white", lw=1.0, zorder=6))

    def ico_table(x, y, s=1.0, c=D3):
        w, h = 3.6 * s, 2.6 * s
        ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=c, lw=0.85, zorder=5))
        ax.add_patch(Rectangle((x, y + h * 0.7), w, h * 0.3, fc=c, ec=c, lw=0.5, zorder=6))
        for k in (1, 2):
            ax.plot([x + w * k / 3] * 2, [y, y + h * 0.7], color=c, lw=0.6, zorder=6)
        ax.plot([x, x + w], [y + h * 0.35] * 2, color=c, lw=0.6, zorder=6)

    def ico_verdict(x, y, ok, s=1.0):
        ax.add_patch(Circle((x, y), 1.55 * s, fc=GREEN if ok else RED, ec="white", lw=0.8, zorder=6))
        if ok:
            ax.plot([x - 0.75 * s, x - 0.15 * s, x + 0.8 * s], [y, y - 0.65 * s, y + 0.6 * s], color="white", lw=1.4,
                    zorder=7, solid_capstyle="round", solid_joinstyle="round")
        else:
            for a, b in ((-1, 1), (1, -1)):
                ax.plot([x - 0.6 * s, x + 0.6 * s], [y + 0.6 * a * s, y + 0.6 * b * s], color="white", lw=1.4, zorder=7,
                        solid_capstyle="round")

    # ---- panels
    card(0.5, 25.5, 99, 24, "#fbfcfe", "#b9c9dd", lw=0.8, r=2)
    card(0.5, 0.5, 99, 23.5, "#fbfdfc", "#b8d9cb", lw=0.8, r=2)
    text(2.4, 47.7, "CONTROL PLANE", size=7.2, bold=True, color=D1, ha="left")
    text(98, 47.7, "trusted; runs when policies or labels change", size=6.8, italic=True, color=MUTED, ha="right")
    text(2.4, 22.0, "DATA PLANE", size=7.2, bold=True, color=D3, ha="left")
    text(14.2, 22.0, "enforcement points, default deny; runs on every flow and tool call", size=6.8, italic=True,
         color=MUTED, ha="left")

    # ---- control plane: inputs
    card(2.5, 28, 21, 17.5, TG, "#c9c9c4")
    text(13, 43.9, "Inputs", size=7.3, bold=True)
    ico_doc(3.9, 37.0, 0.8)
    text(7.6, 38.7, "Intents, constraints,\nreachability queries", size=6.7, ha="left")
    ico_pod(5.3, 34.0, 0.78)
    text(7.6, 34.0, "Pod labels\n(orchestrator)", size=6.7, ha="left")
    ico_badge(5.3, 30.0, 0.78)
    text(7.6, 30.0, "Capability verifier\n(agents, tool servers)", size=6.7, ha="left")

    # ---- control plane: three stages
    stages = [(27, "IMS algebra", "compose  ·  verify  ·  fix\nconflicts and reachability\n(Defs. 1–6)", T1, C1, "∩"),
              (51, "Incremental\ncomposition", "filter and merge only\nthe new triples\n(Lemma 2)", T3, C3, "Δ"),
              (75, "Group compiler", "T: (group, R) → groups\nM: endpoint → group\n(Lemma 1)", T3, C3, None)]
    for x, title, body, fc, ec, glyph in stages:
        card(x, 28, 21.5, 17.5, fc, ec, lw=1.0)
        text(x + 10.75, 41.6, title, size=7.6, bold=True)
        text(x + 10.75, 33.3, body, size=6.8)
        if glyph:
            ax.add_patch(Circle((x + 18.7, 43.1), 1.6, fc="white", ec=ec, lw=0.9, zorder=5))
            text(x + 18.7, 43.05, glyph, size=8.5, bold=True, color=ec)
    ico_table(75 + 16.6, 41.9, 0.6)
    arrow(23.7, 39.0, 26.8, 39.0, lw=1.1)
    arrow(48.7, 36.7, 50.8, 36.7, lw=1.1)
    arrow(72.7, 36.7, 74.8, 36.7, lw=1.1)
    step(27.4, 45.2, 1, C1)
    step(51.4, 45.2, 2, C3)
    step(75.4, 45.2, 3, C3)
    # labels go straight to the membership table M, below the stage cards
    ax.plot([23.7, 23.7, 85.0], [30.0, 26.9, 26.9], color=MUTED, lw=0.9, ls=(0, (3, 2)), zorder=4)
    arrow(85.0, 26.9, 85.0, 27.9, color=MUTED, lw=0.9)
    ax.text(54.0, 26.9, "labels → M: one table write per endpoint event", fontsize=6.6, style="italic", color=MUTED,
            ha="center", va="center", zorder=7, bbox=dict(boxstyle="square,pad=0.15", fc="#fbfcfe", ec="none"))

    # ---- data plane: requests
    card(2.5, 2.5, 30, 17.2, "white", "#d6d6d1")
    text(17.5, 17.9, "Requests", size=7.3, bold=True)
    ico_pod(6.0, 13.8, 0.85)
    ico_pod(9.6, 13.8, 0.85)
    text(12.4, 13.8, "Pod → pod flow\n(src, dst, RPC type)", size=6.7, ha="left")
    ico_robot(7.6, 7.4, 0.95)
    text(11.2, 7.9, "Agent → tool call\n(agent, server, tool, args)", size=6.7, ha="left")
    card(11.0, 2.95, 20.4, 2.2, T2, C2, lw=0.8, r=0.8)
    text(21.2, 4.05, "scope classifier: args → relation R", size=6.5, color=D2)

    # ---- enforcement point
    card(37.0, 2.5, 26.0, 17.2, T1, C1, lw=1.1)
    ico_shield(41.6, 13.2, 1.15)
    text(45.2, 15.6, "Enforcement point", size=7.6, bold=True, ha="left")
    text(45.2, 12.4, "allow iff M[dst] in\nT[M[src]][R]", size=7.0, ha="left")
    text(50.0, 5.9, "2 hash lookups + 1 set lookup\n≈ 12 ns per decision (Rust)", size=6.8, color=D1)
    step(38.1, 19.5, 4, C1)
    arrow(32.8, 13.8, 36.8, 12.8, color=D1, lw=1.1)
    arrow(32.8, 7.4, 36.8, 8.6, color=D3, lw=1.1)

    # ---- outcomes
    card(67.5, 11.3, 30.5, 8.4, "#eef8f2", GREEN, lw=0.9)
    ico_verdict(70.6, 15.5, True, 0.95)
    text(73.0, 17.6, "allow", size=7.3, bold=True, color=GREEN, ha="left")
    text(73.0, 14.2, "to the pod, or to the MCP tool\nserver with a pinned identity", size=6.6, ha="left")
    ico_server(92.4, 13.2, 0.8)
    card(67.5, 2.5, 30.5, 7.6, "#fcefef", RED, lw=0.9)
    ico_verdict(70.6, 6.3, False, 0.95)
    text(73.0, 7.9, "deny", size=7.3, bold=True, color=RED, ha="left")
    text(73.0, 5.0, "flow dropped; the agent gets an error", size=6.6, ha="left")
    arrow(63.2, 12.6, 67.3, 14.6, lw=1.1)
    arrow(63.2, 8.8, 67.3, 6.9, lw=1.1)
    step(66.3, 19.5, 5, C3)

    # ---- compiled policy goes down to the enforcement points
    arrow(86.0, 27.9, 57.0, 19.9, color=C3, lw=1.4)
    ax.text(79.6, 24.4, "T, M", fontsize=7.2, fontweight="bold", color=D3, ha="center", va="center", zorder=7,
            bbox=dict(boxstyle="square,pad=0.15", fc="white", ec="none"))
    fig.tight_layout(pad=0.15)
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


C4, C5, C7 = "#eda100", "#e87ba4", "#6250d6"  # palette slots 4, 5, 7


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=600)
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    plt.close(fig)


MSB_ORDER = ["name_overlap", "preference_manipulation", "prompt_injection", "out_of_scope_parameter", "simulated_user",
             "false_error", "tool_transfer", "search_term_deception", "prompt_injection-simulated_user",
             "prompt_injection-false_error", "preference_manipulation-simulated_user",
             "preference_manipulation-out_of_scope_parameter"]
MSB_SHORT = ["NC", "PM", "PI", "OP", "UI", "FE", "TT", "RI", "PI-UI", "PI-FE", "PM-UI", "PM-OP"]


def fig_radar():
    """E5 radar: share of MSB cases blocked per attack type, for three policy levels."""
    import numpy as np
    with open(os.path.join(RES, "e5.json"), encoding="utf-8") as fh:
        by = json.load(fh)["msb"]["by_type"]
    ang = np.linspace(0, 2 * np.pi, len(MSB_ORDER), endpoint=False)
    fig = plt.figure(figsize=(3.45, 3.25))
    ax = fig.add_subplot(111, polar=True)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    series = [("P1", "Tool-name allow-list (P1)", C2, "--", "s", None),
              ("P2", "AgentSeg, identity pinning (P2)", C1, "-", "o", None),
              ("P3", "AgentSeg, identity + scope (P3)", C3, "-", "^", 0.18)]
    for key, label, col, ls, mk, fill in series:
        v = [100 * by[t][key] / by[t]["cases"] for t in MSB_ORDER]
        a = np.concatenate([ang, ang[:1]])
        vv = v + v[:1]
        ax.plot(a, vv, color=col, ls=ls, lw=1.4, marker=mk, ms=3.6, label=label, zorder=3)
        if fill:
            ax.fill(a, vv, color=col, alpha=fill, zorder=2)
    ax.set_xticks(ang)
    ax.set_xticklabels(MSB_SHORT, fontsize=7.5, color=INK)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100%"], fontsize=6.5, color=MUTED)
    ax.set_rlabel_position(97)
    ax.grid(color=GRID, lw=0.6)
    ax.spines["polar"].set_color(GRID)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=1, fontsize=7, handlelength=2.2)
    fig.tight_layout(pad=0.3)
    save(fig, "e5_radar")


E3_ORDER = ["2", "1", "6", "5", "3", "4", "8", "7", "10", "9", "11"]
E3_NAMES = {"1": "Grafana SSRF", "2": "Node-RED reconnaissance", "3": "Node-RED RCE", "4": "Node-RED container escape",
            "5": "Grafana path traversal", "6": "InfluxDB auth bypass", "7": "runc (CVE-2021-30465)",
            "8": "Kubernetes subpath", "9": "containerd", "10": "runc (CVE-2019-5736)", "11": "Nuclei scan"}


def fig_e3():
    """E3: share of each attack scenario's flows denied, by policy granularity."""
    import numpy as np
    with open(os.path.join(RES, "e3.json"), encoding="utf-8") as fh:
        g = json.load(fh)["granularities"]
    labs = [E3_NAMES[l] for l in E3_ORDER] + ["All attack flows"]
    y = np.arange(len(labs))[::-1]
    fig, ax = plt.subplots(figsize=(3.45, 2.75))
    h = 0.26
    for k, (gr, name, col) in enumerate((("pair+port", "Pair + port (least privilege)", C3),
                                          ("service", "Service (any caller)", C1), ("subnet", "Subnet (/16)", C2))):
        a = g[gr]["attacks_all_benign"]
        vals = [100 * a[l]["blocked_flows"] / a[l]["flows"] for l in E3_ORDER]
        vals.append(100 * sum(v["blocked_flows"] for v in a.values()) / sum(v["flows"] for v in a.values()))
        ax.barh(y + (1 - k) * h, vals, height=h, color=col, label=name, edgecolor="white", linewidth=0.4)
        if gr == "pair+port":
            for yy, v in zip(y, vals):
                ax.text(v + 1.5, yy + h, f"{v:.1f}", va="center", fontsize=6.3, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=7)
    ax.set_xlim(0, 110)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Attack flows denied (%)")
    ax.grid(True, axis="x", color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.axhline(0.5, color=MUTED, lw=0.5)
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.42), fontsize=6.8)  # beside the zero-length rows
    fig.tight_layout(pad=0.3)
    save(fig, "e3_bars")


def fig_e4():
    """E4: red-team authentications denied against legitimate authentications denied in the next 24 h."""
    with open(os.path.join(RES, "e4.json"), encoding="utf-8") as fh:
        e4 = json.load(fh)
    fig, ax = plt.subplots(figsize=(3.45, 2.35))
    styles = {"user_pair": ("User + source + destination", C7, "D", ":"), "pair": ("Source + destination (pair)", C3, "o", "-"),
              "user_dst": ("User + destination", C1, "s", "--"), "dst": ("Destination only", C2, "^", "-.")}
    for key, (name, col, mk, ls) in styles.items():
        xs = [100 * r["next_24h"][key] for r in e4["learn"]]
        ys = [100 * r["kinds"][key]["redteam_denied"] / e4["redteam_events"] for r in e4["learn"]]
        ax.plot(xs, ys, color=col, marker=mk, ms=3.8, ls=ls, lw=1.2, label=name)
        if key in ("pair", "dst"):
            for r, x, yv in zip(e4["learn"], xs, ys):
                if r["hours"] in (6, 41):
                    ax.annotate(f"{r['hours']} h", (x, yv), textcoords="offset points", xytext=(-6, 6 if key == "pair" else 5),
                                fontsize=6.5, color=INK)
    ax.set_xscale("log")
    ax.set_xlabel("Legitimate logons denied in the next 24 h (%, log scale)")
    ax.set_ylabel("Red-team logons denied (%)")
    ax.set_ylim(0, 112)
    style(ax)
    ax.legend(loc="center right", fontsize=6.6)
    fig.tight_layout(pad=0.3)
    save(fig, "e4_tradeoff")


def fig_ablation():
    """Ablation: cost factor when a performance component is removed."""
    import statistics as stt
    ims = collections.defaultdict(list)
    for r in jl("ims_repro.jsonl"):
        if r["exp"] != "epdyn":
            ims[(r["exp"], r["A"], r["B"], r["n"])].append(r["seconds"])
    ab = [stt.mean(ims[(e, False, False, n)]) / stt.mean(ims[(e, True, True, n)])
          for e, n in (("compose", 2000), ("verify", 2000), ("delete", 1000), ("add", 1000))]
    ch = [r for r in jl("e2_churn.jsonl") if r["part"] == "full"]
    ws = sorted({r["window"] for r in ch})
    inc = [stt.mean(r["ims_recompose_s"] for r in ch if r["window"] == w) / stt.mean(r["agentseg_incremental_s"] for r in ch if r["window"] == w) for w in ws]
    with open(os.path.join(RES, "e7_rust.json"), encoding="utf-8") as fh:
        e7 = json.load(fh)
    with open(os.path.join(RES, "e7_python.json"), encoding="utf-8") as fh:
        py = json.load(fh)
    e1 = [r for r in jl("e1.jsonl") if r["k"] == 50]
    e1_pair = stt.mean(r["seconds"] for r in e1 if r["stage"] == "pairwise_compile" and "seconds" in r)
    e1_group = stt.mean(r["seconds"] for r in e1 if r["stage"] == "group_compile")
    rows = [("Group table → per-pair rules\n(lookup, 50-ms subset)", e7["subset_pair_hash_ns"] / e7["subset_group_hash_ns"], None),
            ("Group → per-pair compilation\n(E1, same 50 microservices)", e1_pair / e1_group, None),
            ("Incremental → full recomposition\n(per window; median, range)", stt.median(inc), (min(inc), max(inc))),
            ("IMS optimizations A, B off\n(policy functions; median, range)", stt.median(ab), (min(ab), max(ab))),
            ("Hash-set rows → sorted arrays\n(decision)", e7["group_sorted_ns_observed"] / e7["group_hash_ns_observed"], None),
            ("Rust → Python\n(decision)", py["python_group_ns"] / e7["group_hash_ns_observed"], None)]
    rows = [(a.replace("50-ms", "50-microservice"), b, c) for a, b, c in rows]
    fig, a1 = plt.subplots(figsize=(3.45, 2.3))
    yy = list(range(len(rows)))[::-1]
    a1.barh(yy, [r[1] for r in rows], color=C1, height=0.55, edgecolor="white")
    for y_, (lab, v, rng) in zip(yy, rows):
        if rng:
            a1.plot([rng[0], rng[1]], [y_, y_], color=INK, lw=0.9)
            a1.plot([rng[0]] * 2, [y_ - 0.12, y_ + 0.12], color=INK, lw=0.9)
            a1.plot([rng[1]] * 2, [y_ - 0.12, y_ + 0.12], color=INK, lw=0.9)
        a1.text(max(v, rng[1] if rng else v) * 1.25, y_, (f"{v:,.0f}×" if v >= 100 else f"{v:.1f}×"), va="center",
                fontsize=6.6, color=INK)
    a1.set_yticks(yy)
    a1.set_yticklabels([r[0] for r in rows], fontsize=6.4)
    a1.set_xscale("log")
    a1.set_xlim(1, 3e5)
    a1.set_xlabel("Slowdown when removed (×, log scale)")
    style(a1)
    fig.tight_layout(pad=0.3)
    save(fig, "ablation")


AGENTDOJO_REPORTED = {  # [Debenedetti et al., Table 5]: GPT-4o, all suites, 629 security cases, strongest attack
    "No defense": (69.0, 50.01, 57.69), "Delimiting": (72.66, 55.64, 41.65), "PI detector": (41.49, 21.14, 7.95),
    "Repeat prompt": (85.53, 67.25, 27.82), "Tool filter": (73.13, 56.28, 6.84)}


def fig_agent_compare():
    """Comparison of agent defenses: change in utility under attack and relative reduction of attack success,
    published AgentDojo defenses (GPT-4o) next to AgentSeg in our runs (qwen2.5:1.5b)."""
    with open(os.path.join(RES, "e6.json"), encoding="utf-8") as fh:
        s = json.load(fh)["summary"]
    base = AGENTDOJO_REPORTED["No defense"]
    rows = [(k + " (reported)", 100 * (1 - v[2] / base[2]), v[1] - base[1], "#9aa7b4") for k, v in AGENTDOJO_REPORTED.items() if k != "No defense"]
    for key, name, col in (("agentseg", "AgentSeg, task intents", C1), ("agentseg_scope", "AgentSeg, + parameter scope", C3)):
        rows.append((name, 100 * (1 - s[key]["asr"] / s["none"]["asr"]), 100 * (s[key]["utility_attack"] - s["none"]["utility_attack"]), col))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(3.45, 2.1), sharey=True)
    yy = list(range(len(rows)))[::-1]
    a1.barh(yy, [r[1] for r in rows], color=[r[3] for r in rows], height=0.6, edgecolor="white")
    for y_, r in zip(yy, rows):
        a1.text(r[1] + 2, y_, f"{r[1]:.0f}", va="center", fontsize=6.3, color=INK)
    a1.set_yticks(yy)
    a1.set_yticklabels([r[0] for r in rows], fontsize=6.6)
    a1.set_xlim(0, 125)
    a1.set_xticks([0, 50, 100])
    a1.set_xlabel("Attack success\nreduced (%)", fontsize=7)
    style(a1)
    a2.barh(yy, [r[2] for r in rows], color=[r[3] for r in rows], height=0.6, edgecolor="white")
    for y_, r in zip(yy, rows):
        a2.text(r[2] + (1.5 if r[2] >= 0 else -1.5), y_, f"{r[2]:+.1f}", va="center", ha="left" if r[2] >= 0 else "right",
                fontsize=6.3, color=INK)
    a2.axvline(0, color=MUTED, lw=0.6)
    a2.set_xlim(-50, 30)
    a2.set_xlabel("Utility under attack,\nchange (points)", fontsize=7)
    style(a2)
    fig.tight_layout(pad=0.3, w_pad=0.6)
    save(fig, "agent_compare")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    fig_radar()
    fig_e3()
    fig_e4()
    fig_ablation()
    fig_agent_compare()
    fig_arch()
    fig_e7()
    fig_e1()
    fig_drift()
    fig_churn()
    print("figures written to", OUT)
