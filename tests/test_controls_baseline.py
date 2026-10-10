"""Regression tests: the control tests over the committed, hash-verified baseline evidence
(collected live from the lab) must keep producing exactly these exceptions."""
from itgc.collect.manifest import verify_manifest

from .conftest import BASELINE

EXPECTED = {
    "AC-01": {"hire:mtaylor2", "hire:mbrown", "hire:cadams", "transfer:bnguyen"},
    "AC-02": {"leaver:klee", "leaver:mchen", "leaver:ethomas", "leaver:framirez"},
    "AC-03": {"Active Directory:ahaddad", "Active Directory:svc_backup", "ERP database:ahaddad", "ERP:apatel",
              "ERP-SoD:brivera"},
    "AC-04": {"FY26-Q2-ERP", "FY26-Q3-ADPRIV", "FY26-Q4-ERP"},
    "AC-05": {"domain:minPwdLength", "domain:lockoutThreshold", "frontdesk", "jallen", "mmoore", "pjohnson", "svc_scan"},
    "AC-06": {"ethomas", "gmensah", "klee", "lbaker", "rnovak", "svc_legacyftp"},
    "AC-07": {"frontdesk", "svc_legacyftp", "svc_scan"},
    "CM-01": {"rel-2026-01-13", "rel-2026-03-24", "rel-2026-04-21", "rel-2026-09-17"},
    "CM-02": {"rel-2025-11-25", "rel-2026-06-16", "rel-2026-08-18"},
    "CM-03": set(),
    "CM-04": {"V012"},
    "OPS-01": {"2026-01-28", "2026-06-26"},
    "OPS-02": {"management restore test (FY2026)"},
    "OPS-03": set(),
    "OPS-04": set(),
}


def test_evidence_integrity():
    assert verify_manifest(BASELINE) == []


def test_final_exceptions_match(baseline_results):
    for cid, exp in EXPECTED.items():
        assert set(baseline_results[cid]["final_exception_items"]) == exp, cid


def test_sampled_controls_report_sample_and_final_separately(baseline_results):
    cm01 = baseline_results["CM-01"]
    assert cm01["approach"] == "sample" and cm01["tested"] == 15 and cm01["population_size"] == 32
    assert cm01["sample_conclusion"] == "Effective"          # the random sample happened to miss all 4
    assert cm01["final_conclusion"] == "Not effective"        # the 100% analytic did not
    assert all("outside the sample" in " ".join(r["notes"]) for r in cm01["final_rows"] if r["exception"])


def test_change_population_is_complete(baseline_results):
    c = baseline_results["CM-02"]["completeness"]
    assert c["reconciled"] and c["deployments_in_ci_log"] == c["release_tags_in_git"] == 32


def test_post_termination_logon_is_flagged(baseline_results):
    row = next(r for r in baseline_results["AC-02"]["final_rows"] if r["item"] == "leaver:klee")
    assert row["attrs"] == {"A": "Exception", "B": "Exception", "C": "Pass", "D": "Exception"}


def test_restore_reperformance_passed(baseline_results):
    row = next(r for r in baseline_results["OPS-02"]["final_rows"] if r["item"] == "auditor re-performance")
    assert row["attrs"]["B"] == "Pass" and row["detail"]["tables_mismatched"] == 0
