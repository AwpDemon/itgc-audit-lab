"""Static PNG figures for the README (matplotlib, light surface, reference palette)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .sampling import FREQUENCY_TABLE, detection_probability  # noqa: E402

SURFACE = "#fcfcfb"
INK, INK2, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE = "#2a78d6", "#eb6834"
STATUS = {"Effective": "#0ca30c", "Control deficiency": "#ec835a", "Significant deficiency": "#d03b3b"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
})


def _save(fig, out: Path, name: str) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    p = out / name
    fig.savefig(p, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return p


def control_results(payload: dict, out: Path) -> Path:
    res = payload["results"]
    cls = {d["control_id"]: d["classification"] for d in payload["deficiencies"]}
    ids = list(res)[::-1]
    vals = [len(res[c]["final_exception_items"]) for c in ids]
    status = [cls.get(c, "Effective") for c in ids]
    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    ax.barh(ids, vals, color=[STATUS[s] for s in status], height=0.62, edgecolor=SURFACE, linewidth=2)
    for y, (v, s) in enumerate(zip(vals, status, strict=True)):
        ax.text(v + 0.15, y, f"{v}  {s}", va="center", fontsize=8.5, color=INK2)
    ax.set_xlabel("Exceptions (final, incl. full-population analytics)")
    ax.set_xlim(0, max(vals) + 6)
    ax.grid(axis="y", visible=False)
    ax.set_title("ITGC test results by control - FY2026 lab engagement", loc="left", fontsize=12, color=INK)
    return _save(fig, out, "control_results.png")


def sampling_risk(payload: dict, out: Path) -> Path:
    res = payload["results"]
    cases = []
    cm = res["CM-01"]
    cases.append(("CM-01 changes", cm["population_size"], len(cm["analytic_exception_items"] or []), cm["tested"], BLUE))
    ops = res["OPS-01"]
    cases.append(("OPS-01 backup runs", ops["population_size"], len(ops["final_exception_items"]),
                  FREQUENCY_TABLE["daily"][0], ORANGE))
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    for label, n_pop, k, n_used, color in cases:
        xs = list(range(0, min(n_pop, 120) + 1))
        ys = [detection_probability(n_pop, k, x) for x in xs]
        ax.plot(xs, ys, color=color, linewidth=2, label=f"{label}: {k} bad of {n_pop}")
        p = detection_probability(n_pop, k, n_used)
        ax.plot([n_used], [p], "o", color=color, markersize=8, markeredgecolor=SURFACE, markeredgewidth=2)
        ax.annotate(f"n={n_used}: {p:.0%}", (n_used, p), textcoords="offset points", xytext=(8, -14), fontsize=8.5, color=INK2)
    ax.axhline(0.95, color=AXIS, linewidth=1, linestyle="--")
    ax.text(118, 0.955, "95%", ha="right", va="bottom", fontsize=8, color=INK2)
    ax.set_xlabel("Sample size n")
    ax.set_ylabel("P(sample contains >= 1 exception)")
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Sampling risk: chance a random sample catches at least one exception", loc="left", fontsize=12)
    return _save(fig, out, "sampling_risk.png")


def sample_vs_analytic(payload: dict, out: Path) -> Path:
    res = {k: v for k, v in payload["results"].items() if v["approach"] == "sample" and v.get("analytic_exception_items") is not None}
    ids = list(res)
    s = [len(res[c]["sample_exception_items"]) for c in ids]
    a = [len(res[c]["analytic_exception_items"]) for c in ids]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    x = range(len(ids))
    w = 0.36
    ax.bar([i - w / 2 - 0.01 for i in x], s, w, color=BLUE, label="Found by random sample")
    ax.bar([i + w / 2 + 0.01 for i in x], a, w, color=ORANGE, label="Found by 100% analytic")
    for i in x:
        ax.text(i - w / 2, s[i] + 0.05, str(s[i]), ha="center", fontsize=9, color=INK2)
        ax.text(i + w / 2, a[i] + 0.05, str(a[i]), ha="center", fontsize=9, color=INK2)
    ax.set_xticks(list(x), [f"{c}\n(n={res[c]['tested']} of {res[c]['population_size']})" for c in ids])
    ax.set_ylabel("Exceptions")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False)
    ax.set_title("Same attribute tests: sample vs. full population", loc="left", fontsize=12)
    return _save(fig, out, "sample_vs_analytic.png")


def leaver_timeline(payload: dict, out: Path) -> Path:
    rows = [r for r in payload["results"]["AC-02"]["final_rows"] if "business_days" in r["detail"] or
            r["detail"].get("ad_enabled") is True]
    rows = [r for r in payload["results"]["AC-02"]["final_rows"] if r["detail"].get("ticket")]
    rows.sort(key=lambda r: r["detail"]["termination_date"])
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    for y, r in enumerate(rows):
        d = r["detail"]
        days = d.get("business_days", 0)
        still = d.get("ad_enabled") is True or d.get("erp_active") is True
        color = STATUS["Significant deficiency"] if still else (STATUS["Control deficiency"] if days > 1 else STATUS["Effective"])
        ax.plot([days], [y], "o", color=color, markersize=9, markeredgecolor=SURFACE, markeredgewidth=2)
        label = r["item"].split(":", 1)[1]
        tag = " - still enabled" + (" (AD)" if d.get("ad_enabled") is True else "") + \
              (" (ERP)" if d.get("erp_active") is True else "") if still else ""
        ax.text(days + 0.25, y, f"{label}{tag}", va="center", fontsize=8.5, color=INK2)
    ax.axvline(1, color=AXIS, linestyle="--", linewidth=1)
    ax.text(1.15, -0.9, "standard: 1 business day", fontsize=8, color=INK2)
    ax.set_ylim(-1.3, len(rows) - 0.4)
    ax.set_yticks([])
    ax.set_xlim(-0.5, 14)
    ax.set_xlabel("Business days from termination to ticket closure")
    ax.grid(axis="y", visible=False)
    ax.set_title("Leavers in FY2026: ticket timeliness vs. actual account state", loc="left", fontsize=12)
    return _save(fig, out, "leaver_timeline.png")


def make_figures(payload: dict, out: Path) -> list[Path]:
    return [control_results(payload, out), sampling_risk(payload, out), sample_vs_analytic(payload, out),
            leaver_timeline(payload, out)]


def remediation_chart(before: dict, after: dict, out: Path) -> Path:
    ids = list(before["results"])[::-1]
    b = [len(before["results"][c]["final_exception_items"]) for c in ids]
    a = [len(after["results"][c]["final_exception_items"]) for c in ids]
    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    y = range(len(ids))
    h = 0.36
    ax.barh([i + h / 2 + 0.01 for i in y], b, h, color=BLUE, label="Baseline")
    ax.barh([i - h / 2 - 0.01 for i in y], a, h, color=ORANGE, label="After remediation re-test")
    ax.set_yticks(list(y), ids)
    ax.set_xlabel("Exceptions")
    ax.grid(axis="y", visible=False)
    ax.legend(frameon=False, loc="lower right")
    ax.set_title("Re-test after remediating the lab (config fixes vs. historical process failures)", loc="left", fontsize=11)
    return _save(fig, out, "remediation.png")
