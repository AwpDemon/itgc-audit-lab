"""Compare two audit runs (baseline vs. post-remediation re-test)."""
from __future__ import annotations

import json
from pathlib import Path


def compare(before_dir: Path, after_dir: Path, out_md: Path, fig_dir: Path | None = None) -> str:
    b = json.loads((before_dir / "results.json").read_text(encoding="utf-8"))
    a = json.loads((after_dir / "results.json").read_text(encoding="utf-8"))
    cls_b = {d["control_id"]: d["classification"] for d in b["deficiencies"]}
    cls_a = {d["control_id"]: d["classification"] for d in a["deficiencies"]}
    lines = ["| Control | Baseline exceptions | Re-test exceptions | Closed | Still open | Re-test conclusion |",
             "|---|---:|---:|---|---|---|"]
    tot_b = tot_a = 0
    for cid, rb in b["results"].items():
        ra = a["results"][cid]
        sb, sa = set(rb["final_exception_items"]), set(ra["final_exception_items"])
        tot_b, tot_a = tot_b + len(sb), tot_a + len(sa)
        closed = ", ".join(f"`{x}`" for x in sorted(sb - sa)) or "-"
        still = ", ".join(f"`{x}`" for x in sorted(sa)) or "-"
        concl = ra["final_conclusion"] + (f" ({cls_a[cid]})" if cid in cls_a else "")
        lines.append(f"| {cid} | {len(sb)} | {len(sa)} | {closed} | {still} | {concl} |")
    head = (f"Exceptions: {tot_b} at baseline -> {tot_a} on re-test. Controls not effective: "
            f"{len(cls_b)} -> {len(cls_a)}; significant deficiencies: "
            f"{sum(v == 'Significant deficiency' for v in cls_b.values())} -> "
            f"{sum(v == 'Significant deficiency' for v in cls_a.values())}.")
    out_md.write_text(head + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    if fig_dir:
        from .figures import remediation_chart
        remediation_chart(b, a, fig_dir)
    return head
