"""Deficiency evaluation: classify each control failure and aggregate by risk.

Definitions (PCAOB AS 2201, Appendix A; same concepts in AU-C 265 / ISA 265):
* Control deficiency (CD): design or operation does not allow management or employees, in the
  normal course of their functions, to prevent or detect misstatements on a timely basis.
* Significant deficiency (SD): a deficiency, or combination, less severe than a material
  weakness yet important enough to merit attention by those charged with governance.
* Material weakness (MW): a reasonable possibility that a material misstatement of the
  financial statements will not be prevented or detected on a timely basis.

ITGC deficiencies do not cause misstatements directly; their severity depends on what they
put at risk (automated application controls, reports/IPE, data integrity) and on compensating
controls. This module applies a transparent, documented rule set so the judgement is
reproducible and reviewable; the engagement team would still own the final call, and MW
cannot be concluded from ITGC testing alone (it needs the financial-statement context).

Rule set used here:
1. Any exception in a tested control => the control is "Not effective" => at least a CD
   (expected deviation rate for ITGC tests is zero).
2. Escalate to SD when the deficiency affects a financially significant system AND
   (the risk was *realised* in the evidence, e.g. post-termination logon or an unapproved
   change actually deployed, OR the weakness is *pervasive*, e.g. domain-wide policy or tier-0
   access) AND no *effective* compensating control exists.
3. Aggregate by risk: when two or more key controls addressing the same risk are not
   effective, evaluate the combination; a combination that leaves a risk unmitigated is an SD.
4. Flag SDs that are both realised and pervasive for MW consideration by the engagement team.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .controls.base import FAIL

# Attribute failures that show the risk actually materialised (not just "could happen").
REALISED = {
    "AC-01": {"D", "E"},     # excess access actually granted
    "AC-02": {"A", "B", "D"},  # leaver could still log on / did log on
    "AC-03": {"A", "B"},     # unauthorised privileged access / SoD conflict exists today
    "AC-04": {"C"},          # review said remove, access still there
    "AC-05": set(),          # a weak setting is exposure, not misuse; severity comes from pervasiveness
    "CM-01": {"A", "B"},     # change deployed with no / late approval
    "CM-02": {"B"},          # developer deployed own code
    "CM-03": {"A", "B"},
    "CM-04": {"A"},          # schema changed outside release
    "OPS-01": set(),         # unticketed failure: later backups succeeded -> exposure, not loss
    "OPS-02": set(),
    "OPS-03": {"A"},         # failed GL interface never re-run => GL possibly incomplete
    "OPS-04": set(),
}
# Pervasive = affects every user / the whole platform rather than one account or transaction.
PERVASIVE_ITEMS = ("domain:", "Active Directory:", "ERP database:")


@dataclass
class Evaluation:
    control_id: str
    name: str
    domain: str
    key: bool
    exceptions: int
    tested: int
    realised: bool
    pervasive: bool
    compensating: list[str]
    compensating_effective: bool
    classification: str
    mw_consideration: bool
    rationale: list[str] = field(default_factory=list)


@dataclass
class Aggregate:
    risk_id: str
    risk: str
    controls: list[str]
    classification: str
    rationale: str


def evaluate(results: dict[str, dict], rcm: dict) -> tuple[list[Evaluation], list[Aggregate]]:
    """results: control_id -> {'rows': [...], 'final_conclusion': ..., ...} as built by the engine."""
    controls = {c["id"]: c for c in rcm["controls"]}
    evals: list[Evaluation] = []
    for cid, res in results.items():
        if res["final_conclusion"] == "Effective":
            continue
        c = controls[cid]
        bad_rows = [r for r in res["final_rows"] if r["exception"]]
        failed_attrs = {a for r in bad_rows for a, v in r["attrs"].items() if v == FAIL}
        realised = bool(failed_attrs & REALISED.get(cid, set()))
        pervasive = any(r["item"].startswith(PERVASIVE_ITEMS) for r in bad_rows)
        comp = c.get("compensating_controls", []) or []
        comp_ok = bool(comp) and all(results.get(x, {}).get("final_conclusion") == "Effective" for x in comp)
        why = [f"{len(bad_rows)} exception(s) in {res['tested']} item(s) tested; tolerable deviation rate is 0 -> control not effective."]
        if realised:
            why.append("Risk realised in the evidence (failed attribute(s) " + ", ".join(sorted(failed_attrs & REALISED[cid])) + ").")
        else:
            why.append("No evidence the risk was realised (exposure only).")
        if pervasive:
            why.append("Pervasive: affects domain-wide settings or tier-0/database administration.")
        if comp:
            why.append(f"Compensating control(s) {', '.join(comp)} " + ("effective." if comp_ok else
                       "NOT effective - cannot be relied on."))
        sd = (realised or pervasive) and not comp_ok
        cls = "Significant deficiency" if sd else "Control deficiency"
        mw = sd and realised and pervasive
        if mw:
            why.append("Realised AND pervasive: escalate for material-weakness consideration (requires the "
                       "financial-statement impact assessment, outside ITGC scope).")
        evals.append(Evaluation(cid, c["name"], c["domain"], bool(c.get("key")), len(bad_rows), res["tested"],
                                realised, pervasive, comp, comp_ok, cls, mw, why))
    # Aggregation by risk
    aggs: list[Aggregate] = []
    failing = {e.control_id: e for e in evals}
    for rid, text in rcm["risks"].items():
        addressed = [c["id"] for c in rcm["controls"] if rid in c["risk"]]
        bad = [cid for cid in addressed if cid in failing]
        effective = [cid for cid in addressed if cid not in failing]
        if len(bad) >= 2:
            unmitigated = not effective
            cls = "Significant deficiency" if (unmitigated or any(failing[b].classification == "Significant deficiency"
                                                                   for b in bad)) else "Control deficiency"
            rationale = (f"{len(bad)} of {len(addressed)} controls addressing this risk are not effective "
                         f"({', '.join(bad)}); " + ("no control addressing it is effective - risk unmitigated."
                                                    if unmitigated else f"remaining effective: {', '.join(effective)}."))
            aggs.append(Aggregate(rid, text, bad, cls, rationale))
    return evals, aggs
