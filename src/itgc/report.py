"""Management letter (condition / criteria / cause / effect / recommendation) and a results summary."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from .dates import PERIOD_END, PERIOD_START

# Likely cause and recommendation per control. Causes are hypotheses an associate would
# confirm with management before issuing the letter, and are labelled that way.
TEXT = {
    "AC-01": ("New-hire and transfer access is not consistently approved, matched to the request, or cleaned up on transfer",
              "Access is fulfilled from verbal/e-mail requests when tickets lag; transfer tickets record removals but no "
              "one verifies AD after closure.",
              "Block account creation in the provisioning workflow until manager approval is recorded; fulfil from the "
              "role baseline in the ticket only; add a post-fulfilment check that compares AD groups with the request "
              "and, for transfers, confirms prior-role groups were removed."),
    "AC-02": ("Terminated users retained access to Active Directory and the ERP",
              "Termination tickets are closed on the HR side without confirming the AD account and the separate ERP "
              "user were disabled; there is no automated HR-to-AD reconciliation.",
              "Disable AD and ERP access automatically from the HR termination event (or same-day ticket with "
              "verification step); run a weekly HR-terminated vs. enabled-account reconciliation; investigate the "
              "post-termination logon for data access and notify the incident process."),
    "AC-03": ("Privileged access and segregation-of-duties conflicts are not restricted to authorised personnel",
              "Privileged groups are granted for convenience (troubleshooting, backups) and never removed; the "
              "authorised list is not reconciled to the systems; the ERP has no preventive SoD rule set.",
              "Remove the unauthorised Domain Admin, ERP_ADMIN and database SUPERUSER rights; give service accounts "
              "least privilege (Backup Operators / pg_read_all_data); implement a preventive SoD rule set in the ERP "
              "role-assignment workflow; reconcile privileged groups to the authorised list monthly."),
    "AC-04": ("Quarterly user access reviews were late, not independent, or not followed through",
              "Review evidence is tracked by e-mail; removals are ticketed but closure is not verified against the "
              "system; reviewer assignment does not exclude reviewers' own accounts.",
              "Track review due dates in the GRC/ITSM tool with escalation at day 20; assign privileged-group reviews "
              "to someone who holds no privileged access; require system evidence (screenshot or export) before a "
              "removal ticket can be closed."),
    "AC-05": ("Domain password and lockout settings are weaker than ISS-04, and some accounts bypass the policy",
              "The default domain policy was not updated when ISS-04 v3.1 was approved; account flags are set ad hoc "
              "by IT to stop help-desk calls.",
              "Set minimum length 12 and lockout threshold 5 in the default domain policy (or move to passphrases + "
              "MFA); clear DONT_EXPIRE_PASSWORD on user accounts and PASSWD_NOTREQD everywhere; monitor these flags "
              "with a scheduled LDAP query."),
    "AC-06": ("Dormant accounts were not disabled after 90 days of inactivity",
              "The monthly inactive-account report is not run consistently and has no owner sign-off.",
              "Automate disabling at 90 days (with HR leave-of-absence exceptions approved in advance); keep the "
              "monthly report as evidence with sign-off."),
    "AC-07": ("Service and generic accounts are not inventoried, owned, or prohibited as required",
              "Service accounts are created by project teams without registering them; owners are not updated "
              "when people leave; a shared reception login was never replaced.",
              "Register every service account with a current owner and review annually; move to group-managed "
              "service accounts where possible; replace the shared login with named accounts (or a kiosk mode "
              "without ERP access)."),
    "CM-01": ("Production changes were deployed without a ticket, approval or testing evidence",
              "The pipeline does not check for an approved change ticket before deploying.",
              "Make the production deployment job require an approved change ID (pipeline gate) and attach UAT "
              "evidence to the ticket; report deployments without tickets monthly to the CAB."),
    "CM-02": ("A developer deployed their own changes to production",
              "Pipeline permissions allow any Domain Admin to run the production job; the developer holds Domain "
              "Admin rights (see AC-03).",
              "Restrict the production pipeline to PRD-Deployers and enforce 'author != deployer' in the pipeline; "
              "review the three self-deployed releases for unauthorised content."),
    "CM-03": ("Emergency changes were not retrospectively approved on time",
              "No tracking of open emergency changes awaiting retro-approval.",
              "Auto-create a retro-approval task due in 2 business days for every hotfix deployment; escalate overdue "
              "items to the IT Manager."),
    "CM-04": ("A database schema change was applied directly in production outside the release process",
              "A developer holds database SUPERUSER (see AC-03) and applied a hotfix manually.",
              "Remove developer superuser access; alert on schema_migrations rows not written by the pipeline account; "
              "retroactively review and approve or reverse the direct change."),
    "OPS-01": ("Backup failures were not always followed up",
               "Failure e-mails go to a shared mailbox without ticket automation.",
               "Create incidents automatically from backup-job failures; report consecutive failures to the IT Manager "
               "the same day."),
    "OPS-02": ("No restore test was performed during the year",
               "Restore testing is not scheduled or owned.",
               "Schedule an annual (preferably quarterly) restore test with documented validation (row counts / "
               "checksums) and measured restore time against the RTO."),
    "OPS-03": ("A failed ERP-to-GL interface run had no ticket or re-run evidence",
               "Interface monitoring relies on someone noticing the failure e-mail.",
               "Alert on failed runs, require a ticket and confirm the successful re-run and GL completeness "
               "(record counts) before closing."),
    "OPS-04": ("A P1 incident was closed without a root-cause analysis",
               "Problem records are optional in the ITSM workflow.",
               "Make a linked problem record with RCA mandatory before a P1 can be closed."),
}


def _condition_lines(cid: str, res: dict, limit: int = 10) -> list[str]:
    lines = []
    attrs = {}
    for row in res["final_rows"]:
        if not row["exception"]:
            continue
        failed = [a for a, v in row["attrs"].items() if v == "Exception"]
        attrs[row["item"]] = failed
        d = {k: v for k, v in row["detail"].items() if v not in (None, "", [], {})}
        bits = ", ".join(f"{k}: {v}" for k, v in list(d.items())[:7])
        outside = " (found outside the sample)" if any("outside the sample" in n for n in row["notes"]) else ""
        lines.append(f"`{row['item']}` - failed attribute(s) {', '.join(failed)}{outside}; {bits}")
    if len(lines) > limit:
        extra = len(lines) - limit
        lines = lines[:limit] + [f"... and {extra} more (see workpaper {cid})."]
    return lines


def write_letter(path: Path, ev, rcm: dict, results: dict, evals, aggs) -> Path:
    controls = {c["id"]: c for c in rcm["controls"]}
    order = sorted(evals, key=lambda e: (e.classification != "Significant deficiency", e.control_id))
    n_bad = len(evals)
    sds = [e for e in evals if e.classification == "Significant deficiency"]
    out = [
        "# Management Letter - IT General Controls",
        "",
        "**To:** Chief Financial Officer and Audit Committee, Kestrel Valve Co. *(fictional company - portfolio lab)*  ",
        f"**Period:** {PERIOD_START:%d %B %Y} to {PERIOD_END:%d %B %Y}  ",
        f"**Evidence:** bundle `{ev.root.name}` collected {ev.manifest.get('collected_at', 'n/a')} (SHA-256 manifest)  ",
        f"**Date:** {date.today():%d %B %Y}",
        "",
        "> This letter is generated from code over evidence pulled from a lab environment. The company, people and "
        "tickets are synthetic; the directory, database and repository evidence was collected live from the lab "
        "systems. Management responses are placeholders - in a real engagement they are obtained before issue.",
        "",
        "## 1. Scope and approach",
        "",
        "We tested the design and operating effectiveness of 15 IT general controls over Active Directory, the ERP "
        "application and database, and the ERP release pipeline, across three SOX ITGC domains: access to programs "
        "and data, program changes, and computer operations. Evidence was obtained directly from the systems with "
        "read-only accounts (LDAPS, PostgreSQL `pg_read_all_data`, git) and from management-provided documents. "
        "Where populations were machine-readable we tested 100% with data analytics; otherwise we selected random "
        "samples sized by control frequency and risk. Deviations found outside a sample were evaluated as well.",
        "",
        "## 2. Summary",
        "",
        f"* **{len(results) - n_bad} of {len(results)}** controls operated effectively; **{n_bad}** were not effective.",
        f"* **{len(sds)}** deficiencies are classified as **significant deficiencies**; the rest are control deficiencies.",
        f"* **{sum(e.mw_consideration for e in evals)}** are flagged for material-weakness consideration by the engagement "
        "team (realised and pervasive; the final assessment needs the financial-statement context).",
        "",
        "| # | Control | Finding | Classification |",
        "|---|---|---|---|",
    ]
    for i, e in enumerate(order, start=1):
        out.append(f"| {i} | {e.control_id} | {TEXT[e.control_id][0]} | {e.classification} |")
    if aggs:
        out += ["", "**Aggregated deficiencies (by risk):**", ""]
        for a in aggs:
            out.append(f"* **{a.risk_id}** - {a.risk} Controls not effective: {', '.join(a.controls)}. "
                       f"**{a.classification}.** {a.rationale}")
    out += ["", "## 3. Findings", ""]
    for i, e in enumerate(order, start=1):
        c = controls[e.control_id]
        res = results[e.control_id]
        title, cause, rec = TEXT[e.control_id]
        out += [f"### {i}. {title}", "",
                f"*Control {e.control_id} - {c['name']} | {c['domain']} | {e.classification}*", "",
                f"**Condition.** We tested {res['tested']} item(s) from a population of {res['population_size']} "
                f"({res['selection']}) and noted {e.exceptions} exception(s):", ""]
        out += [f"- {line}" for line in _condition_lines(e.control_id, res)]
        out += ["", f"**Criteria.** {c['objective']} ({c['criteria']}).", "",
                f"**Cause (likely - to be confirmed with management).** {cause}", "",
                "**Effect / risk.** " + " ".join(rcm["risks"][r] for r in c["risk"]) + " " + " ".join(e.rationale[1:]), "",
                f"**Recommendation.** {rec}", "",
                f"**Framework references.** COBIT 2019 {', '.join(c['cobit'])}; NIST SP 800-53 Rev. 5 {', '.join(c['nist'])}; "
                f"SOC 2 TSC {', '.join(c['soc2'])}.", "",
                "**Management response.** *[To be obtained from the control owner: action, owner, target date.]*", ""]
    eff = [cid for cid, r in results.items() if r["final_conclusion"] == "Effective"]
    out += ["## 4. Controls operating effectively", ""]
    out += [f"* {cid} - {results[cid]['name']}" for cid in eff] or ["* None."]
    other = []
    for cid in ("OPS-01", "OPS-02", "AC-05"):
        for n in results[cid]["notes"]:
            if n.startswith(("Observation", "Auditor re-performance", "Scope limitation")):
                other.append(f"* {cid}: {n}")
    if other:
        out += ["", "## 5. Other observations", ""] + other
    out += ["", "---", "*Prepared by Ali Askari as a portfolio lab engagement. Not an audit opinion.*", ""]
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")
    return path


def write_summary_md(path: Path, results: dict, evals, aggs, scoring: dict | None) -> Path:
    cls = {e.control_id: e.classification for e in evals}
    out = ["| Control | Name | Approach | N | Tested | Exceptions (sample) | Exceptions (final) | Conclusion | Classification |",
           "|---|---|---|---:|---:|---:|---:|---|---|"]
    for cid, r in results.items():
        out.append(f"| {cid} | {r['name']} | {r['approach']} | {r['population_size']} | {r['tested']} | "
                   f"{len(r['sample_exception_items'])} | {len(r['final_exception_items'])} | {r['final_conclusion']} | "
                   f"{cls.get(cid, '-')} |")
    if scoring:
        out += ["", f"Planted issues detected: {scoring['detected']}/{scoring['planted']} "
                f"(sample-only approach on sampled controls: {scoring['sampled_controls_found_by_sample']}/"
                f"{scoring['sampled_controls_planted']}; with full-population analytics: "
                f"{scoring['sampled_controls_found_by_analytic']}/{scoring['sampled_controls_planted']})."]
        if scoring["extras"]:
            out += ["", "Exceptions not in the answer key:", ""]
            out += [f"* {x['control_id']} `{x['item']}` - {x['kind']}" for x in scoring["extras"]]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    return path
