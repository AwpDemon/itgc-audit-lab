"""IT operations control tests (SOX ITGC domain: Computer Operations)."""
from __future__ import annotations

from ..dates import PERIOD_END, PERIOD_START, business_days_between, parse_date
from ..evidence import Evidence
from ..sampling import select
from .base import FAIL, Row, TestResult, run_sampled, verdict


def _streaks(days: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    for d in sorted(days):
        if out and (parse_date(d) - parse_date(out[-1][-1])).days == 1:
            out[-1].append(d)
        else:
            out.append([d])
    return out


# --------------------------------------------------------------------------- OPS-01
def test_ops01(ev: Evidence) -> TestResult:
    log = [r for r in ev.pbc.get("backup_job_log", []) if PERIOD_START <= parse_date(r["run_date"]) <= PERIOD_END]
    failures = [r for r in log if r["status"] != "Success"]
    rows = [Row(r["run_date"], {"A": verdict(bool(r["ticket"]))},
                {"status": r["status"], "ticket": r["ticket"] or "none", "start": r["start"]}) for r in failures]
    streaks = [s for s in _streaks([r["run_date"] for r in failures]) if len(s) >= 2]
    notes = [f"{len(log)} runs in period, {len(failures)} failed ({len(failures) / max(len(log), 1):.1%})."]
    for s in streaks:
        notes.append(f"Observation: {len(s)} consecutive failed nights {s[0]} to {s[-1]} - recovery point "
                     f"exposure of {len(s) + 1} days.")
    # Counterfactual: what a traditional 20-day random sample of daily runs would have shown
    sample = select([r["run_date"] for r in log], 20, "FY2026:OPS-01-traditional")
    hit = [d for d in sample if d in {r["run_date"] for r in failures}]
    notes.append(f"Sampling study: a traditional random sample of 20 daily runs would have contained "
                 f"{len(hit)} failed run(s) ({', '.join(hit) or 'none'}).")
    res = TestResult("OPS-01", "analytic", "All nightly ERP backup runs in the period (scheduler log); failures tested",
                     len(log), len(failures), "100% of failed runs identified by analytic over the full job log", rows,
                     notes=notes)
    res.completeness = {"runs": len(log), "expected_days": (PERIOD_END - PERIOD_START).days + 1}
    return res


# --------------------------------------------------------------------------- OPS-02
def test_ops02(ev: Evidence) -> TestResult:
    tests = [t for t in ev.pbc.get("restore_test_log", []) if PERIOD_START <= parse_date(t["date"]) <= PERIOD_END]
    last = max((t["date"] for t in ev.pbc.get("restore_test_log", [])), default=None)
    rows = [Row("management restore test (FY2026)", {"A": verdict(bool(tests)), "B": "N/A"},
                {"tests_in_period": len(tests), "most_recent_test": last})]
    r = ev.restore
    notes = []
    if r:
        ok = r.get("tables_mismatched", 1) == 0
        rows.append(Row("auditor re-performance", {"A": "N/A", "B": verdict(ok)},
                        {"database": r["database"], "backup_seconds": r["backup_seconds"],
                         "restore_seconds": r["restore_seconds"], "total_seconds": r["total_seconds"],
                         "dump_bytes": r["dump_bytes"], "tables": len(r["tables"]),
                         "rows_restored": sum(t["restored_rows"] for t in r["tables"]),
                         "tables_mismatched": r["tables_mismatched"], "performed_at": r["performed_at"]}))
        notes.append("Auditor re-performance proves the backup mechanism works today; it does NOT cure the "
                     "control failure (management did not perform the control during the period).")
    return TestResult("OPS-02", "sample", "Restore tests in the period (annual control -> test of one)",
                      len(tests), 1, "Annual control: 1 occurrence expected", rows, notes=notes)


# --------------------------------------------------------------------------- OPS-03
def test_ops03(ev: Evidence) -> TestResult:
    log = [r for r in ev.pbc.get("batch_job_log", []) if PERIOD_START <= parse_date(r["run_date"]) <= PERIOD_END]
    failures = [r for r in log if r["status"] != "Success"]
    rows = [Row(r["run_date"], {"A": verdict(bool(r["ticket"]) and r["rerun_status"] == "Success")},
                {"ticket": r["ticket"] or "none", "rerun": r["rerun_status"] or "none"}) for r in failures]
    return TestResult("OPS-03", "analytic", "All ERP-to-GL interface runs in the period; failures tested", len(log),
                      len(failures), "100% of failed runs identified by analytic over the full job log", rows,
                      notes=[f"{len(log)} business-day runs, {len(failures)} failed."])


# --------------------------------------------------------------------------- OPS-04
def test_ops04(ev: Evidence) -> TestResult:
    limit = ev.standard["operations"]["incident"]["p1_rca_within_business_days"]
    p1 = {i["incident_id"]: i for i in ev.pbc.get("incidents", []) if i["priority"] == "P1"
          and PERIOD_START <= parse_date(i["opened_at"]) <= PERIOD_END}

    def evaluate(inc_id: str) -> Row:
        i = p1[inc_id]
        if not i["rca_completed_on"]:
            return Row(inc_id, {"A": FAIL}, {"opened": i["opened_at"], "rca": "none"})
        days = business_days_between(parse_date(i["opened_at"]), parse_date(i["rca_completed_on"]))
        return Row(inc_id, {"A": verdict(days <= limit)}, {"opened": i["opened_at"], "rca": i["rca_reference"],
                                                          "business_days": days})

    return run_sampled("OPS-04", ev, sorted(p1), evaluate, risk="low", population_desc="P1 incidents in the period")
