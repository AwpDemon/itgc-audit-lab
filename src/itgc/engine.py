"""Run the whole audit on one evidence bundle and write every deliverable."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import yaml

from .collect.manifest import verify_manifest
from .controls import REGISTRY
from .deficiency import evaluate
from .evidence import Evidence
from .scoring import score

ROOT = Path(__file__).resolve().parents[2]


def load_rcm(path: Path | None = None) -> dict:
    return yaml.safe_load((path or ROOT / "audit" / "rcm" / "rcm.yaml").read_text(encoding="utf-8"))


def run_tests(ev: Evidence, rcm: dict) -> dict[str, dict]:
    """Execute every RCM control test; returns control_id -> serialisable result with final conclusions."""
    out: dict[str, dict] = {}
    for c in rcm["controls"]:
        res = REGISTRY[c["id"]](ev)
        d = res.to_dict()
        sample_exc = d["exception_items"]
        if res.analytic_rows is not None:
            # Deviations found outside the sample must still be evaluated (cannot be ignored).
            extra = [r for r in res.analytic_rows if r.has_exception and r.item not in sample_exc]
            final_rows = d["rows"] + [{"item": r.item, "attrs": r.attrs, "detail": r.detail,
                                       "notes": r.notes + ["Identified outside the sample by full-population analytic."],
                                       "exception": True} for r in extra]
        else:
            final_rows = d["rows"]
        final_items = [r["item"] for r in final_rows if r["exception"]]
        d.update({"name": c["name"], "domain": c["domain"], "key": c.get("key", False),
                  "tested": d["sample_size"], "sample_exception_items": sample_exc,
                  "sample_conclusion": "Not effective" if sample_exc else "Effective",
                  "final_rows": final_rows, "final_exception_items": final_items,
                  "final_conclusion": "Not effective" if final_items else "Effective"})
        out[c["id"]] = d
    return out


def run_audit(evidence_dir: Path, out_dir: Path, figures: bool = True) -> str:
    from .report import write_letter, write_summary_md
    from .workpapers import write_workpapers

    problems = verify_manifest(evidence_dir)
    if problems:
        raise SystemExit("Evidence integrity check failed:\n" + "\n".join(problems))
    ev = Evidence.load(evidence_dir)
    rcm = load_rcm()
    results = run_tests(ev, rcm)
    evals, aggs = evaluate(results, rcm)
    key = ROOT / "lab" / "seed" / "answer_key.json"
    scoring = score(results, key) if key.exists() else None
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"evidence": evidence_dir.name, "evidence_manifest_generated_at": ev.manifest.get("generated_at"),
               "results": results, "deficiencies": [asdict(e) for e in evals],
               "aggregates": [asdict(a) for a in aggs], "scoring": scoring}
    (out_dir / "results.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8", newline="\n")
    write_workpapers(out_dir / "ITGC_workpapers.xlsx", ev, rcm, results, evals, aggs)
    write_letter(out_dir / "management_letter.md", ev, rcm, results, evals, aggs)
    write_summary_md(out_dir / "summary.md", results, evals, aggs, scoring)
    if figures:
        from .figures import make_figures
        make_figures(payload, ROOT / "docs" / "figures" if evidence_dir.name == "fy26-baseline" else out_dir / "figures")
    n_bad = sum(1 for r in results.values() if r["final_conclusion"] != "Effective")
    sds = sum(1 for e in evals if e.classification == "Significant deficiency")
    lines = [f"controls tested: {len(results)}  not effective: {n_bad}  significant deficiencies: {sds}  "
             f"aggregates: {len(aggs)}"]
    if scoring:
        lines.append(f"planted issues detected: {scoring['detected']}/{scoring['planted']}")
    lines.append(f"outputs: {out_dir}")
    return "\n".join(lines)
