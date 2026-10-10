"""Logical access control tests (SOX ITGC domain: Access to Programs and Data)."""
from __future__ import annotations

from datetime import UTC, datetime

from ..ad import PRIVILEGED_AD_GROUPS
from ..dates import PERIOD_END, PERIOD_START, business_days_between, parse_date, parse_dt
from ..evidence import Evidence
from .base import FAIL, NA, PASS, Row, TestResult, account_kind, run_sampled, verdict

SOD_RULES = [("AP_CLERK", "AP_APPROVER", "Enter vendor invoices + approve payments"),
             ("GL_POSTER", "GL_APPROVER", "Post + approve journal entries")]


def _split(v: str | None) -> set[str]:
    return {x for x in (v or "").split(";") if x}


def _ad_for_person(ev: Evidence, hr_row: dict) -> dict | None:
    emp = hr_row["employee_id"]
    for u in ev.users:
        if u.get("employee_id") == emp and account_kind(u) == "person":
            return u
    return ev.user(hr_row["network_id"])


# --------------------------------------------------------------------------- AC-01
def test_ac01(ev: Evidence) -> TestResult:
    hires = [h for h in ev.hr if PERIOD_START <= parse_date(h["hire_date"]) <= PERIOD_END]
    requests = {r["account"].lower(): r for r in ev.pbc.get("access_requests", []) if r["type"] == "new_hire"}
    transfers = ev.pbc.get("transfer_tickets", [])
    added_later = {}
    for t in transfers:
        added_later.setdefault(t["account"].lower(), set()).update(_split(t["groups_to_add"]))
    hr_by_emp = ev.hr_by_emp()
    rows: list[Row] = []
    for h in sorted(hires, key=lambda x: x["hire_date"]):
        sam = h["network_id"].lower()
        ad = _ad_for_person(ev, h)
        req = requests.get(sam)
        created = parse_dt(ad["when_created"]) if ad else None
        a = req is not None
        b = c = d = None
        detail: dict[str, object] = {"hire_date": h["hire_date"], "ad_created": ad["when_created"] if ad else None,
                                     "ticket": req["ticket_id"] if req else None}
        if req:
            approved = parse_dt(req["approved_at"])
            b = created is not None and approved <= created
            mgr = hr_by_emp.get(h["manager_employee_id"], {})
            c = req["approver"].lower() == (mgr.get("network_id") or "").lower()
            detail |= {"approved_at": req["approved_at"], "approver": req["approver"]}
            allowed = _split(req["requested_groups"]) | added_later.get(sam, set())
            excess = sorted(set(ad["member_of"]) - allowed) if ad else []
            d = not excess
            if excess:
                detail["excess_groups"] = excess
        rows.append(Row(f"hire:{sam}", {"A": verdict(a), "B": verdict(b), "C": verdict(c), "D": verdict(d), "E": NA},
                        detail))
    for t in transfers:
        sam = t["account"].lower()
        ad = ev.user(sam)
        member = set(ad["member_of"]) if ad else set()
        retained = sorted(_split(t["groups_to_remove"]) & member)
        missing = sorted(_split(t["groups_to_add"]) - member)
        rows.append(Row(f"transfer:{sam}", {"A": PASS, "B": NA, "C": NA, "D": verdict(not missing), "E": verdict(not retained)},
                        {"ticket": t["ticket_id"], "effective": t["effective_date"], "retained_groups": retained,
                         "missing_groups": missing}))
    # Completeness: AD person accounts created in the period must map to an HR hire
    hire_sams = {h["network_id"].lower() for h in hires}
    unexpected = []
    for u in ev.users:
        created = parse_dt(u.get("when_created"))
        if account_kind(u) in ("person", "admin") and created and PERIOD_START <= created.date() <= PERIOD_END \
                and u["sam"].lower() not in hire_sams:
            unexpected.append(u["sam"])
    for sam in unexpected:
        rows.append(Row(f"unexpected:{sam}", {"A": FAIL, "B": NA, "C": NA, "D": NA, "E": NA},
                        {"reason": "AD account created in period with no HR hire record"}))
    return TestResult("AC-01", "analytic", "New hires (HR) in period + transfers", len(hires) + len(transfers),
                      len(hires) + len(transfers), "100% of population (population below sampling threshold)",
                      rows, completeness={"hr_hires": len(hires), "ad_accounts_created_in_period_not_in_hr": unexpected})


# --------------------------------------------------------------------------- AC-02
def test_ac02(ev: Evidence) -> TestResult:
    leavers = [h for h in ev.hr if h["employment_status"] == "Terminated"]
    tickets = {t["account"].lower(): t for t in ev.pbc.get("termination_tickets", [])}
    max_days = ev.standard["logical_access"]["termination"]["disable_within_business_days"]
    rows = []
    for h in sorted(leavers, key=lambda x: x["termination_date"]):
        sam = h["network_id"].lower()
        term = parse_date(h["termination_date"])
        in_period = PERIOD_START <= term <= PERIOD_END
        ad = _ad_for_person(ev, h)
        erp = ev.erp_user(sam)
        a = ad is None or not ad["enabled"]
        b = erp is None or not erp["is_active"]
        c = None
        detail: dict[str, object] = {"termination_date": h["termination_date"],
                                     "ad_enabled": ad["enabled"] if ad else "not found",
                                     "erp_active": erp["is_active"] if erp else "not found"}
        if in_period:
            t = tickets.get(sam)
            if t is None:
                c = False
                detail["ticket"] = "none"
            else:
                days = business_days_between(term, parse_date(t["completed_at"]))
                c = days <= max_days
                detail |= {"ticket": t["ticket_id"], "completed": t["completed_at"], "business_days": days}
        last = parse_dt(ad.get("last_logon_timestamp")) if ad else None
        d = None if last is None else last.date() <= term
        if last:
            detail["last_logon"] = last.isoformat()
        row = Row(f"leaver:{sam}", {"A": verdict(a), "B": verdict(b), "C": verdict(c), "D": verdict(d)}, detail)
        if d is False:
            row.notes.append("lastLogonTimestamp after termination: conclusive evidence of post-termination use "
                             "(replication lag can only make the timestamp older, never newer).")
        rows.append(row)
    return TestResult("AC-02", "analytic", "All employees HR lists as terminated (timeliness for in-period leavers)",
                      len(leavers), len(leavers), "100% of population (data analytic)", rows)


# --------------------------------------------------------------------------- AC-03
def test_ac03(ev: Evidence) -> TestResult:
    auth = ev.pbc.get("authorized_privileged_access", [])
    allowed = {(r["system"], r["account"].lower()) for r in auth}
    privs: dict[str, set[str]] = {}
    for g in PRIVILEGED_AD_GROUPS:
        for m in ev.priv_groups.get(g, []):
            privs.setdefault(f"Active Directory|{m.lower()}", set()).add(g)
    for u in ev.erp_users:
        if "ERP_ADMIN" in u["roles"] and u["is_active"]:
            privs.setdefault(f"ERP|{u['username'].lower()}", set()).add("ERP_ADMIN")
    for r in ev.db_roles:
        if r["superuser"] and r["can_login"]:
            privs.setdefault(f"ERP database|{r['role'].lower()}", set()).add("SUPERUSER")
    developers = {m.lower() for m in ev.priv_groups.get("DEV-Developers", [])}
    deployers = {m.lower() for m in ev.priv_groups.get("PRD-Deployers", [])}
    rows = []
    for key in sorted(privs):
        system, acct = key.split("|")
        ok = (system, acct) in allowed
        conflict = acct in developers
        rows.append(Row(f"{system}:{acct}", {"A": verdict(ok), "B": verdict(not conflict)},
                        {"privileges": sorted(privs[key]),
                         "sod": "Developer with production administrative rights" if conflict else ""}))
    for d in sorted(developers & deployers):
        rows.append(Row(f"PRD-Deployers:{d}", {"A": FAIL, "B": FAIL}, {"privileges": ["PRD-Deployers"],
                        "sod": "Developer can deploy to production"}))
    sod_hits = 0
    for u in ev.erp_users:
        if not u["is_active"]:
            continue
        roles = set(u["roles"])
        bad = [desc for r1, r2, desc in SOD_RULES if {r1, r2} <= roles]
        if bad:
            sod_hits += 1
            rows.append(Row(f"ERP-SoD:{u['username'].lower()}", {"A": NA, "B": FAIL},
                            {"roles": sorted(roles), "sod": "; ".join(bad)}))
    active_erp = sum(1 for u in ev.erp_users if u["is_active"])
    return TestResult("AC-03", "analytic",
                      "All privileged AD/ERP/DB accounts + SoD rule set over all active ERP users",
                      len(privs) + active_erp, len(privs) + active_erp, "100% of population (data analytic)", rows,
                      notes=[f"SoD rule set run over {active_erp} active ERP users; {sod_hits} with conflicts listed."])


# --------------------------------------------------------------------------- AC-04
def test_ac04(ev: Evidence) -> TestResult:
    signoffs = {s["review_id"]: s for s in ev.pbc.get("uar_signoffs", [])}
    detail_rows = ev.pbc.get("uar_detail", [])
    limit = ev.standard["logical_access"]["user_access_review"]["complete_within_days_of_quarter_end"]
    admins = {m.lower() for g in PRIVILEGED_AD_GROUPS for m in ev.priv_groups.get(g, [])}
    erp_admins = {u["username"].lower() for u in ev.erp_users if "ERP_ADMIN" in u["roles"]}

    def evaluate(review_id: str) -> Row:
        s = signoffs[review_id]
        days = (parse_date(s["signed_off_on"]) - parse_date(s["quarter_end"])).days
        reviewer = s["reviewer"].lower()
        if s["system"] == "ERP":
            independent = reviewer not in erp_admins
        else:
            independent = reviewer not in admins and f"adm-{reviewer}" not in admins
        removals = [d for d in detail_rows if d["review_id"] == review_id and d["decision"] == "Remove"]
        not_done = []
        for d in removals:
            u = ev.user(d["account"])
            erp = ev.erp_user(d["account"])
            if (u and d["entitlement"] in u["member_of"]) or (erp and d["entitlement"] in erp["roles"]):
                not_done.append(f"{d['account']} still has {d['entitlement']}")
        c = None if not removals else not not_done
        return Row(review_id, {"A": verdict(days <= limit), "B": verdict(independent), "C": verdict(c)},
                   {"system": s["system"], "quarter_end": s["quarter_end"], "signed_off": s["signed_off_on"],
                    "days_after_qe": days, "reviewer": s["reviewer"], "removals_requested": len(removals),
                    "removals_not_actioned": not_done})

    res = None
    rows, analytic = [], []
    for system in sorted({s["system"] for s in signoffs.values()}):
        ids = [k for k, s in signoffs.items() if s["system"] == system]
        part = run_sampled("AC-04", ev, ids, evaluate, risk="high", frequency="quarterly", key=f"AC-04:{system}")
        rows += part.rows
        analytic += part.analytic_rows or []
        res = part
    return TestResult("AC-04", "sample", "Quarterly access-review sign-offs, stratified by system (2 x 4 quarters)",
                      len(signoffs), len(rows), (res.selection if res else "") + " per system", rows,
                      analytic_rows=analytic)


# --------------------------------------------------------------------------- AC-05
def test_ac05(ev: Evidence) -> TestResult:
    std = ev.standard["logical_access"]
    p = ev.policy
    checks = [
        ("domain:minPwdLength", p.get("min_pwd_length"), f">= {std['password']['min_length']}",
         (p.get("min_pwd_length") or 0) >= std["password"]["min_length"]),
        ("domain:complexity", p.get("complexity_enabled"), "enabled", bool(p.get("complexity_enabled"))),
        ("domain:pwdHistoryLength", p.get("history_length"), f">= {std['password']['history_length']}",
         (p.get("history_length") or 0) >= std["password"]["history_length"]),
        ("domain:maxPwdAge", p.get("max_pwd_age_days"), f"1-{std['password']['max_age_days']} days",
         0 < (p.get("max_pwd_age_days") or 0) <= std["password"]["max_age_days"]),
        ("domain:minPwdAge", p.get("min_pwd_age_days"), f">= {std['password']['min_age_days']} day",
         (p.get("min_pwd_age_days") or 0) >= std["password"]["min_age_days"]),
        ("domain:lockoutThreshold", p.get("lockout_threshold"), f"1-{std['lockout']['threshold']} attempts",
         0 < (p.get("lockout_threshold") or 0) <= std["lockout"]["threshold"]),
        ("domain:lockoutDuration", p.get("lockout_duration_minutes"), f">= {std['lockout']['duration_minutes']} min",
         (p.get("lockout_duration_minutes") or 0) >= std["lockout"]["duration_minutes"]),
    ]
    rows = [Row(item, {"A": verdict(ok)}, {"actual": actual, "required": req}) for item, actual, req, ok in checks]
    inventory = {r["account"].lower(): r for r in ev.pbc.get("service_account_inventory", [])}
    enabled = [u for u in ev.users if u["enabled"] and account_kind(u) != "auditor"]
    for u in sorted(enabled, key=lambda x: x["sam"].lower()):
        flags = set(u["uac_flags"])
        issues = []
        if "DONT_EXPIRE_PASSWORD" in flags:
            inv = inventory.get(u["sam"].lower())
            if not (account_kind(u) == "service" and inv and inv.get("password_never_expires_exception") == "Approved"):
                issues.append("DONT_EXPIRE_PASSWORD without approved exception")
        if "PASSWD_NOTREQD" in flags:
            issues.append("PASSWD_NOTREQD (password not required)")
        if issues:
            rows.append(Row(u["sam"].lower(), {"A": FAIL}, {"kind": account_kind(u), "flags": sorted(flags),
                                                            "issue": "; ".join(issues)}))
    notes = [f"userAccountControl decoded for all {len(enabled)} enabled accounts; only non-compliant accounts listed.",
             "Domain policy is an automated control: a test of one is sufficient when ITGCs over change to it are effective."]
    if not p.get("fine_grained_policies"):
        notes.append("Scope limitation: " + p.get("fine_grained_policies_note", ""))
    return TestResult("AC-05", "analytic", "Domain password/lockout policy + all enabled accounts' UAC flags",
                      len(checks) + len(enabled), len(checks) + len(enabled), "Test of one (automated setting) + 100% analytic",
                      rows, notes=notes)


# --------------------------------------------------------------------------- AC-06
def test_ac06(ev: Evidence) -> TestResult:
    std = ev.standard["logical_access"]["dormant_accounts"]
    limit = std["disable_after_days_inactive"] + std["replication_tolerance_days"]
    asof = datetime.combine(PERIOD_END, datetime.max.time()).replace(tzinfo=UTC)
    pop = []
    rows = []
    for u in ev.users:
        if not u["enabled"] or account_kind(u) == "auditor":
            continue
        created = parse_dt(u.get("when_created"))
        if created and created.date() > PERIOD_END:
            continue                       # did not exist at period end
        pop.append(u)
        last = parse_dt(u.get("last_logon_timestamp"))
        ref = last or created
        idle = (asof - ref).days if ref else None
        ok = idle is not None and idle <= limit
        if not ok:
            rows.append(Row(u["sam"].lower(), {"A": FAIL}, {"kind": account_kind(u), "last_logon": u.get("last_logon_timestamp"),
                                                            "days_inactive_at_period_end": idle}))
    return TestResult("AC-06", "analytic", "All enabled AD accounts existing at period end", len(pop), len(pop),
                      "100% of population (data analytic)", rows,
                      notes=[f"Threshold {std['disable_after_days_inactive']} days + {std['replication_tolerance_days']}-day "
                             "lastLogonTimestamp replication tolerance; only exceptions listed."])


# --------------------------------------------------------------------------- AC-07
def test_ac07(ev: Evidence) -> TestResult:
    inventory = {r["account"].lower(): r for r in ev.pbc.get("service_account_inventory", [])}
    hr = ev.hr_by_sam()
    rows = []
    pop = [u for u in ev.users if u["enabled"] and account_kind(u) in ("service", "generic")]
    for u in sorted(pop, key=lambda x: x["sam"].lower()):
        sam = u["sam"].lower()
        if account_kind(u) == "generic":
            rows.append(Row(sam, {"A": NA, "B": NA, "C": FAIL}, {"description": u.get("description"),
                                                                   "groups": u["member_of"]}))
            continue
        inv = inventory.get(sam)
        owner = (inv or {}).get("owner") or ""
        owner_hr = hr.get(owner.lower())
        a = bool(inv and owner)
        b = None if not a else bool(owner_hr and owner_hr["employment_status"] != "Terminated")
        rows.append(Row(sam, {"A": verdict(a), "B": verdict(b), "C": PASS},
                        {"owner": owner or None, "owner_status": owner_hr["employment_status"] if owner_hr else None,
                         "description": u.get("description")}))
    return TestResult("AC-07", "analytic", "All enabled service and generic AD accounts", len(pop), len(pop),
                      "100% of population (data analytic)", rows)


__all__ = ["test_ac01", "test_ac02", "test_ac03", "test_ac04", "test_ac05", "test_ac06", "test_ac07", "PASS"]
