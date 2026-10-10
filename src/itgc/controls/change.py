"""Change management control tests (SOX ITGC domain: Program Changes)."""
from __future__ import annotations

from ..dates import business_days_between, parse_date, parse_dt
from ..evidence import Evidence
from .base import FAIL, NA, Row, TestResult, run_sampled, verdict


def _sam_from_email(email: str) -> str:
    return (email or "").split("@", 1)[0].lower()


def _tickets_by_tag(ev: Evidence) -> dict[str, dict]:
    return {t["release_tag"]: t for t in ev.pbc.get("change_tickets", []) if t.get("release_tag")}


def _completeness(ev: Evidence) -> dict[str, object]:
    deployed = {d["tag"] for d in ev.deploy_log}
    tagged = {t["tag"] for t in ev.tags}
    return {"deployments_in_ci_log": len(deployed), "release_tags_in_git": len(tagged),
            "deployed_without_tag": sorted(deployed - tagged), "tagged_without_deployment": sorted(tagged - deployed),
            "reconciled": deployed == tagged}


# --------------------------------------------------------------------------- CM-01
def test_cm01(ev: Evidence) -> TestResult:
    tickets = _tickets_by_tag(ev)
    deploys = {d["tag"]: d for d in ev.deploy_log}

    def evaluate(tag: str) -> Row:
        d = deploys[tag]
        t = tickets.get(tag)
        deployed = parse_dt(d["deployed_at"])
        if t is None:
            return Row(tag, {"A": FAIL, "B": NA, "C": NA, "D": NA}, {"deployed_at": d["deployed_at"],
                       "deployed_by": d["deployed_by"], "ticket": "none"})
        emergency = t["type"] == "Emergency"
        b = None if emergency else parse_dt(t["approved_at"]) <= deployed
        c = True if emergency else bool(t["test_evidence"].strip() and t["uat_signoff_by"].strip())
        dd = t["approver"].lower() != t["developer"].lower()
        row = Row(tag, {"A": verdict(True), "B": verdict(b), "C": verdict(c), "D": verdict(dd)},
                  {"ticket": t["change_id"], "type": t["type"], "approved_at": t["approved_at"],
                   "deployed_at": d["deployed_at"], "approver": t["approver"], "developer": t["developer"],
                   "test_evidence": t["test_evidence"] or "(blank)"})
        if emergency:
            row.notes.append("Emergency change: approval timing tested under CM-03.")
        return row

    res = run_sampled("CM-01", ev, sorted(deploys), evaluate, risk="high",
                      population_desc="Production deployments (CI/CD log reconciled to git tags)")
    res.completeness = _completeness(ev)
    return res


# --------------------------------------------------------------------------- CM-02
def test_cm02(ev: Evidence) -> TestResult:
    deployers = {m.lower() for m in ev.priv_groups.get("PRD-Deployers", [])}
    tags = {t["tag"]: t for t in ev.tags}
    rows = []
    for d in sorted(ev.deploy_log, key=lambda x: x["deployed_at"]):
        who = d["deployed_by"].lower()
        authors = sorted({_sam_from_email(c["author_email"]) for c in tags.get(d["tag"], {}).get("commits", [])})
        rows.append(Row(d["tag"], {"A": verdict(who in deployers), "B": verdict(who not in authors)},
                        {"deployed_by": d["deployed_by"], "commit_authors": authors, "deployed_at": d["deployed_at"]}))
    return TestResult("CM-02", "analytic", "All production deployments in the period", len(rows), len(rows),
                      "100% of population (data analytic)", rows, completeness=_completeness(ev),
                      notes=["Deployer authorization uses current PRD-Deployers membership as the best available "
                             "evidence of membership during the period (group history is not retained by AD)."])


# --------------------------------------------------------------------------- CM-03
def test_cm03(ev: Evidence) -> TestResult:
    tickets = _tickets_by_tag(ev)
    deploys = {d["tag"]: d for d in ev.deploy_log}
    limit = ev.standard["change_management"]["emergency_retro_approval_within_business_days"]
    emergency = sorted({t["release_tag"] for t in tickets.values() if t["type"] == "Emergency"}
                       | {tag for tag in deploys if tag.endswith("-hotfix")})

    def evaluate(tag: str) -> Row:
        t = tickets.get(tag)
        if t is None:
            return Row(tag, {"A": FAIL, "B": NA}, {"ticket": "none"})
        days = business_days_between(parse_date(deploys[tag]["deployed_at"]), parse_date(t["approved_at"]))
        return Row(tag, {"A": verdict(True), "B": verdict(days <= limit)},
                   {"ticket": t["change_id"], "deployed_at": deploys[tag]["deployed_at"],
                    "approved_at": t["approved_at"], "business_days_to_approval": days})

    return run_sampled("CM-03", ev, emergency, evaluate, risk="high", population_desc="Emergency (hotfix) releases")


# --------------------------------------------------------------------------- CM-04
def test_cm04(ev: Evidence) -> TestResult:
    shipped = {}
    for t in ev.tags:
        for f in t.get("migrations", []):
            shipped[f.split("__", 1)[0]] = t["tag"]
    deploy_at = {d["tag"]: parse_dt(d["deployed_at"]) for d in ev.deploy_log}
    rows = []
    for m in ev.migrations:
        tag = shipped.get(m["version"])
        a = tag is not None
        b = m["applied_by"] == "erp_owner"
        detail = {"applied_at": m["applied_at"], "applied_by": m["applied_by"], "release": tag}
        if tag and tag in deploy_at:
            detail["minutes_after_deploy"] = round((parse_dt(m["applied_at"]) - deploy_at[tag]).total_seconds() / 60, 1)
        rows.append(Row(m["version"], {"A": verdict(a), "B": verdict(b)}, detail))
    return TestResult("CM-04", "analytic", "Every row in production public.schema_migrations", len(rows), len(rows),
                      "100% of population (data analytic)", rows)
