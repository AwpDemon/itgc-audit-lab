"""Score audit detections against the scenario's answer key (planted issues).

The control tests never read the answer key. Scoring happens afterwards and answers:
* recall   - how many planted issues did the audit procedures find?
* sampling - which planted issues would a sample-only approach have missed?
* extras   - exceptions that were not planted: either a knock-on effect of a planted issue
             seen through another control, or something genuinely unplanned.
"""
from __future__ import annotations

import json
from pathlib import Path


def norm(item: str) -> str:
    """Strip test-specific prefixes ('hire:', 'leaver:', 'Active Directory:', ...) to the entity."""
    item = item.strip()
    for prefix in ("hire:", "transfer:", "leaver:", "unexpected:", "ERP-SoD:", "PRD-Deployers:",
                   "Active Directory:", "ERP database:", "ERP:"):
        if item.startswith(prefix):
            return item[len(prefix):].lower()
    return item.lower() if not item.startswith(("domain:", "rel-", "FY", "V", "INC-", "management")) else item


def score(results: dict[str, dict], answer_key_path: Path) -> dict:
    key = json.loads(answer_key_path.read_text(encoding="utf-8"))["issues"]
    final = {cid: {norm(i) for i in r["final_exception_items"]} for cid, r in results.items()}
    sample = {cid: {norm(i) for i in r["sample_exception_items"]} for cid, r in results.items()}
    planted_entities = {norm(k["item"]) for k in key}
    rows = []
    for k in key:
        ent = norm(k["item"])
        cid = k["control_id"]
        rows.append({**k, "detected": ent in final.get(cid, set()),
                     "detected_by_sample_only_approach": ent in sample.get(cid, set()),
                     "approach": results[cid]["approach"]})
    extras = []
    planted_pairs = {(k["control_id"], norm(k["item"])) for k in key}
    for cid, items in final.items():
        for ent in sorted(items):
            if (cid, ent) not in planted_pairs:
                extras.append({"control_id": cid, "item": ent,
                               "kind": "knock-on of a planted issue (same entity planted under another control)"
                               if ent in planted_entities else "not planted"})
    detected = sum(r["detected"] for r in rows)
    sampled_rows = [r for r in rows if r["approach"] == "sample"]
    return {"planted": len(rows), "detected": detected, "recall": detected / len(rows) if rows else 0.0,
            "sampled_controls_planted": len(sampled_rows),
            "sampled_controls_found_by_sample": sum(r["detected_by_sample_only_approach"] for r in sampled_rows),
            "sampled_controls_found_by_analytic": sum(r["detected"] for r in sampled_rows),
            "issues": rows, "extras": extras}
