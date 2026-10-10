from pathlib import Path

from itgc.deficiency import evaluate
from itgc.scoring import norm, score

ROOT = Path(__file__).resolve().parents[1]


def _res(item, attrs, concl="Not effective"):
    return {"final_conclusion": concl, "tested": 10,
            "final_rows": [{"item": item, "attrs": attrs, "exception": "Exception" in attrs.values(), "notes": []}]}


RCM = {"risks": {"R1": "risk one"}, "controls": [
    {"id": "AC-06", "name": "dormant", "domain": "APD", "key": False, "risk": ["R1"]},
    {"id": "AC-02", "name": "leaver", "domain": "APD", "key": True, "risk": ["R1"], "compensating_controls": ["AC-06"]},
    {"id": "AC-05", "name": "pwd", "domain": "APD", "key": True, "risk": ["R1"]}]}


def test_exposure_only_is_control_deficiency_and_pervasive_is_significant():
    results = {"AC-06": _res("x", {"A": "Exception"}),
               "AC-05": _res("domain:minPwdLength", {"A": "Exception"}),
               "AC-02": _res("leaver:y", {"A": "Pass", "B": "Pass", "C": "Exception", "D": "Pass"})}
    evals, aggs = evaluate(results, RCM)
    by = {e.control_id: e for e in evals}
    assert by["AC-06"].classification == "Control deficiency"
    assert by["AC-05"].classification == "Significant deficiency" and by["AC-05"].pervasive
    assert by["AC-02"].classification == "Control deficiency"      # timeliness (C) alone is not "realised"
    assert aggs and aggs[0].classification == "Significant deficiency"   # every control on R1 failed


def test_effective_compensating_control_prevents_escalation():
    results = {"AC-06": _res("x", {"A": "Pass"}, concl="Effective"),
               "AC-05": _res("u", {"A": "Pass"}, concl="Effective"),
               "AC-02": _res("leaver:y", {"A": "Exception", "B": "Pass", "C": "Pass", "D": "Pass"})}
    evals, _ = evaluate(results, RCM)
    assert evals[0].realised and evals[0].compensating_effective
    assert evals[0].classification == "Control deficiency"


def test_scoring_normalisation():
    assert norm("leaver:KLee") == "klee" and norm("Active Directory:svc_backup") == "svc_backup"
    assert norm("rel-2026-01-13") == "rel-2026-01-13" and norm("domain:minPwdLength") == "domain:minPwdLength"


def test_baseline_detects_every_planted_issue(baseline_results):
    s = score(baseline_results, ROOT / "lab" / "seed" / "answer_key.json")
    assert s["detected"] == s["planted"] == 39
    assert all(x["kind"].startswith("knock-on") for x in s["extras"])
    assert s["sampled_controls_found_by_sample"] == 2 and s["sampled_controls_found_by_analytic"] == 8
