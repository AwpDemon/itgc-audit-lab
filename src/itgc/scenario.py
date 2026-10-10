"""Deterministic generator for the fictional company "Kestrel Valve Co." used by the lab.

It produces three kinds of output, kept deliberately separate:

1. **System seeds** (``lab/.build/``): the directory spec loaded into the Samba AD domain
   controller, the SQL that builds the ERP database, and the change history used to build
   the application's git repository + CI/CD deployment log. These become the *systems*
   the audit collects evidence from.
2. **PBC documents** (``audit/pbc/``): what management would hand an auditor ("provided by
   client"): HR roster, ITSM ticket exports, access-review sign-offs, job logs, policies.
3. **Answer key** (``lab/seed/answer_key.json``): the list of issues deliberately planted.
   The control tests never read it; it is only used afterwards to score how many planted
   issues the audit procedures detected (and to show sampling risk).

Everything is driven by one seeded RNG, so a re-run reproduces identical output.
All people, names and the company are fictional.
"""
from __future__ import annotations

import csv
import json
import random
import string
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .dates import (
    PERIOD_END,
    PERIOD_START,
    add_business_days,
    is_business_day,
)

SEED = 2026
COMPANY = "Kestrel Valve Co."
MAIL_DOMAIN = "kestrel-valve.example"   # RFC 2606 reserved TLD: cannot be a real mailbox
REALM_DN = "DC=kestrel,DC=lab,DC=test"

FIRST = """James Mary Robert Patricia John Jennifer Michael Linda David Elizabeth William Barbara
Richard Susan Joseph Jessica Thomas Sarah Charles Karen Christopher Lisa Daniel Nancy Matthew
Betty Anthony Margaret Mark Sandra Donald Ashley Steven Kimberly Paul Emily Andrew Donna Joshua
Michelle Kenneth Carol Kevin Amanda Brian Melissa George Deborah Timothy Stephanie Ronald Rebecca
Jason Sharon Edward Laura Jeffrey Cynthia Ryan Amy Jacob Angela Gary Helen Nicholas Anna Eric
Brenda Jonathan Pamela Priya Wei Carlos Aisha Mohammed Mei Diego Fatima Hiroshi Olga""".split()
LAST = """Smith Johnson Williams Brown Jones Garcia Miller Davis Rodriguez Martinez Hernandez Lopez
Gonzalez Wilson Anderson Thomas Taylor Moore Jackson Martin Lee Perez Thompson White Harris
Sanchez Clark Ramirez Lewis Robinson Walker Young Allen King Wright Scott Torres Nguyen Hill
Flores Green Adams Nelson Baker Hall Rivera Campbell Mitchell Carter Roberts Patel Kim Chen Okafor
Kowalski Novak Haddad Ivanova Tanaka Mensah Larsen Fischer Moreau Rossi Silva Costa""".split()

# (department, title, headcount at period end, AD groups, ERP roles)
ORG = [
    ("Executive", "Chief Executive Officer", 1, ["VPN-Users"], ["VIEWER"]),
    ("Executive", "Chief Financial Officer", 1, ["VPN-Users", "FS-Finance-RW"], ["VIEWER"]),
    ("Executive", "Chief Operating Officer", 1, ["VPN-Users"], ["VIEWER"]),
    ("Executive", "VP Sales", 1, ["VPN-Users"], ["SALES", "VIEWER"]),
    ("Finance", "Controller", 1, ["VPN-Users", "FS-Finance-RW", "APP-ERP-GL-Approver", "APP-ERP-AP-Approver"], ["GL_APPROVER", "AP_APPROVER"]),
    ("Finance", "AP Clerk", 3, ["FS-Finance-RW", "APP-ERP-AP-Clerk"], ["AP_CLERK"]),
    ("Finance", "AP Manager", 1, ["FS-Finance-RW", "APP-ERP-AP-Approver"], ["AP_APPROVER"]),
    ("Finance", "GL Accountant", 3, ["FS-Finance-RW", "APP-ERP-GL-Poster"], ["GL_POSTER"]),
    ("Finance", "Payroll Specialist", 1, ["FS-Finance-RW", "FS-HR-RW"], ["VIEWER"]),
    ("Finance", "Financial Analyst", 2, ["FS-Finance-RW"], ["VIEWER"]),
    ("Human Resources", "HR Director", 1, ["FS-HR-RW", "VPN-Users"], []),
    ("Human Resources", "HR Generalist", 2, ["FS-HR-RW"], []),
    ("Sales", "Sales Manager", 2, ["VPN-Users"], ["SALES"]),
    ("Sales", "Account Executive", 10, ["VPN-Users"], ["SALES"]),
    ("Sales", "Sales Operations Analyst", 2, [], ["SALES", "VIEWER"]),
    ("Operations", "Plant Manager", 1, ["VPN-Users"], ["BUYER", "VIEWER"]),
    ("Operations", "Production Supervisor", 3, [], ["VIEWER"]),
    ("Operations", "Machinist", 9, [], []),
    ("Operations", "Buyer", 3, [], ["BUYER"]),
    ("Operations", "Logistics Coordinator", 3, [], ["VIEWER"]),
    ("Operations", "Quality Engineer", 2, [], []),
    ("Information Technology", "IT Manager", 1, ["VPN-Users", "IT-Staff"], []),
    ("Information Technology", "Systems Administrator", 2, ["VPN-Users", "IT-Staff"], []),
    ("Information Technology", "Help Desk Technician", 2, ["IT-Staff", "IT-Helpdesk"], []),
    ("Information Technology", "Database Administrator", 1, ["VPN-Users", "IT-Staff", "DBA-Admins"], []),
    ("Engineering", "Development Manager", 1, ["VPN-Users", "DEV-Developers"], []),
    ("Engineering", "Software Developer", 4, ["VPN-Users", "DEV-Developers"], []),
    ("Engineering", "Release Manager", 1, ["VPN-Users", "PRD-Deployers"], []),
]
ERP_GROUP_ROLES = {"APP-ERP-AP-Clerk": "AP_CLERK", "APP-ERP-AP-Approver": "AP_APPROVER",
                   "APP-ERP-GL-Poster": "GL_POSTER", "APP-ERP-GL-Approver": "GL_APPROVER"}
DEPT_GROUP = {"Executive": "GG-Executive", "Finance": "GG-Finance", "Human Resources": "GG-HR",
              "Sales": "GG-Sales", "Operations": "GG-Operations",
              "Information Technology": "GG-IT", "Engineering": "GG-Engineering"}
GROUP_DESCRIPTIONS = {
    "GG-AllStaff": "All employees", "VPN-Users": "Remote access VPN",
    "FS-Finance-RW": "Finance file share (read/write)", "FS-HR-RW": "HR file share (read/write)",
    "APP-ERP-Users": "ERP application - base access", "APP-ERP-AP-Clerk": "ERP - enter vendor invoices / vendor master",
    "APP-ERP-AP-Approver": "ERP - approve payments", "APP-ERP-GL-Poster": "ERP - post journal entries",
    "APP-ERP-GL-Approver": "ERP - approve journal entries", "IT-Staff": "IT department staff",
    "IT-Helpdesk": "Delegated password reset", "DBA-Admins": "Database administration",
    "DEV-Developers": "Application developers (non-production)", "PRD-Deployers": "Production deployment rights",
    "GG-ServiceAccounts": "Service accounts (fine-grained password policy target)",
}


@dataclass
class Person:
    emp_id: str
    first: str
    last: str
    sam: str
    dept: str
    title: str
    hire_date: date
    status: str = "active"            # active | terminated | leave
    term_date: date | None = None
    manager_emp_id: str | None = None
    groups: list[str] = field(default_factory=list)
    erp_roles: list[str] = field(default_factory=list)
    prior_dept: str | None = None
    prior_title: str | None = None
    transfer_date: date | None = None

    @property
    def display(self) -> str:
        return f"{self.first} {self.last}"


def _dt(d: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(d, time(hour, minute))


def _iso(x: date | datetime | None) -> str:
    if x is None:
        return ""
    return x.isoformat(timespec="seconds") if isinstance(x, datetime) else x.isoformat()


def _rand_date(rng: random.Random, start: date, end: date, business: bool = True) -> date:
    while True:
        d = start + timedelta(days=rng.randrange((end - start).days + 1))
        if not business or is_business_day(d):
            return d


def _password(rng: random.Random) -> str:
    alphabet = string.ascii_letters + string.digits
    return "Lab-" + "".join(rng.choice(alphabet) for _ in range(14)) + "!9"


class Scenario:
    def __init__(self, seed: int = SEED):
        self.rng = random.Random(seed)
        self.people: list[Person] = []
        self.answer_key: list[dict] = []
        self._used_sams: set[str] = set()
        self._emp_seq = 1000
        self._names: set[tuple[str, str]] = set()
        # outputs
        self.access_requests: list[dict] = []
        self.termination_tickets: list[dict] = []
        self.transfer_tickets: list[dict] = []
        self.service_accounts: list[dict] = []
        self.ad_accounts: list[dict] = []        # spec rows for the DC seeder
        self.erp_users: list[dict] = []
        self.db_roles: list[dict] = []
        self.releases: list[dict] = []
        self.change_tickets: list[dict] = []
        self.migrations_applied: list[dict] = []
        self.uar_signoffs: list[dict] = []
        self.uar_detail: list[dict] = []
        self.backup_log: list[dict] = []
        self.batch_log: list[dict] = []
        self.incidents: list[dict] = []
        self.restore_tests: list[dict] = []
        self.authorized_priv: list[dict] = []
        self.ticket_seq = {"AR": 0, "TRM": 0, "TRF": 0, "CHG": 0, "INC": 0, "UAR": 0}

    # ------------------------------------------------------------------ helpers
    def plant(self, issue_id: str, control: str, item: str, description: str) -> None:
        self.answer_key.append({"issue_id": issue_id, "control_id": control, "item": item,
                                "description": description})

    def _ticket(self, prefix: str) -> str:
        self.ticket_seq[prefix] += 1
        return f"{prefix}-{self.ticket_seq[prefix]:05d}"

    def _new_name(self) -> tuple[str, str]:
        while True:
            pair = (self.rng.choice(FIRST), self.rng.choice(LAST))
            if pair not in self._names:
                self._names.add(pair)
                return pair

    def _sam_for(self, first: str, last: str) -> str:
        base = (first[0] + last).lower()
        sam, n = base, 1
        while sam in self._used_sams:
            n += 1
            sam = f"{base}{n}"
        self._used_sams.add(sam)
        return sam

    def _person(self, dept: str, title: str, hire: date, groups: list[str], roles: list[str]) -> Person:
        first, last = self._new_name()
        self._emp_seq += 1
        p = Person(emp_id=f"E{self._emp_seq}", first=first, last=last, sam=self._sam_for(first, last),
                   dept=dept, title=title, hire_date=hire)
        p.groups = ["GG-AllStaff", DEPT_GROUP[dept], *groups]
        if roles:
            p.groups.append("APP-ERP-Users")
        p.erp_roles = list(roles)
        return p

    def by_title(self, title: str, status: str = "active") -> list[Person]:
        return [p for p in self.people if p.title == title and p.status == status]

    # ------------------------------------------------------------------ build
    def build(self) -> Scenario:
        self._build_people()
        self._build_lifecycle_tickets()
        self._build_ad_accounts()
        self._build_erp()
        self._build_changes()
        self._build_uar()
        self._build_operations()
        return self

    def _build_people(self) -> None:
        rng = self.rng
        roster: list[Person] = []
        for dept, title, count, groups, roles in ORG:
            for _ in range(count):
                hire = _rand_date(rng, date(2012, 1, 1), date(2025, 6, 30))
                roster.append(self._person(dept, title, hire, groups, roles))
        # 14 of the non-executive staff were hired during the audit period
        eligible = [p for p in roster if p.dept != "Executive" and p.title not in
                    ("IT Manager", "Controller", "Development Manager", "Plant Manager", "HR Director")]
        for p in rng.sample(eligible, 14):
            p.hire_date = _rand_date(rng, PERIOD_START + timedelta(days=5), PERIOD_END - timedelta(days=10))
        # Leavers during the period (11) and before the period (5): extra people, roles back-filled
        leaver_titles = ["AP Clerk", "Account Executive", "Account Executive", "Machinist", "Buyer",
                         "GL Accountant", "Software Developer", "Help Desk Technician", "Sales Manager",
                         "Logistics Coordinator", "Quality Engineer"]
        lookup = {t: (d, g, r) for d, t, _, g, r in ORG}
        for title in leaver_titles:
            d, g, r = lookup[title]
            p = self._person(d, title, _rand_date(rng, date(2014, 1, 1), date(2024, 12, 31)), g, r)
            p.status = "terminated"
            p.term_date = _rand_date(rng, PERIOD_START + timedelta(days=10), PERIOD_END - timedelta(days=20))
            roster.append(p)
        for title in ["Machinist", "Account Executive", "Buyer", "HR Generalist", "Financial Analyst"]:
            d, g, r = lookup[title]
            p = self._person(d, title, _rand_date(rng, date(2013, 1, 1), date(2021, 12, 31)), g, r)
            p.status = "terminated"
            p.term_date = _rand_date(rng, date(2024, 1, 15), PERIOD_START - timedelta(days=30))
            roster.append(p)
        # managers: department head = first person with a "head" title, else the CEO
        heads = {"Finance": "Controller", "Human Resources": "HR Director", "Sales": "VP Sales",
                 "Operations": "Plant Manager", "Information Technology": "IT Manager",
                 "Engineering": "Development Manager", "Executive": "Chief Executive Officer"}
        head_ids = {d: next(p.emp_id for p in roster if p.title == t) for d, t in heads.items()}
        ceo = head_ids["Executive"]
        for p in roster:
            p.manager_emp_id = ceo if p.emp_id in head_ids.values() else head_ids[p.dept]
            if p.emp_id == ceo:
                p.manager_emp_id = None
        self.people = roster
        # One employee is on leave of absence (HR status) - relevant to dormant-account testing
        on_leave = rng.choice(self.by_title("Quality Engineer"))
        on_leave.status = "leave"
        # Two movers (department transfers) during the period
        mover1 = rng.choice([p for p in self.by_title("GL Accountant") if p.hire_date < PERIOD_START])
        mover2 = rng.choice([p for p in self.by_title("Logistics Coordinator") if p.hire_date < PERIOD_START])
        for mover, (nd, nt) in ((mover1, ("Finance", "Financial Analyst")),
                                (mover2, ("Operations", "Buyer"))):
            mover.prior_dept, mover.prior_title = mover.dept, mover.title
            mover.transfer_date = _rand_date(rng, date(2026, 1, 5), date(2026, 6, 30))
            d, g, r = lookup[nt]
            mover.dept, mover.title = nd, nt
            new_groups = ["GG-AllStaff", DEPT_GROUP[nd], *g] + (["APP-ERP-Users"] if r else [])
            old_groups = mover.groups
            mover.groups = new_groups
            mover.erp_roles = list(r)
            mover._old_groups = old_groups          # type: ignore[attr-defined]
        self.mover_planted = mover1                 # retains old access (planted M1)
        self.mover_clean = mover2

    def _build_lifecycle_tickets(self) -> None:
        rng = self.rng
        hires = sorted([p for p in self.people if PERIOD_START <= p.hire_date <= PERIOD_END],
                       key=lambda p: p.hire_date)
        self.hires = hires
        no_ticket, late_approval, excess = rng.sample(hires, 3)
        self.prov_dates: dict[str, datetime] = {}
        for p in hires:
            prov = _dt(add_business_days(p.hire_date, -rng.randint(1, 3)), rng.randint(9, 16), rng.randint(0, 59))
            self.prov_dates[p.sam] = prov
            requested = list(p.groups)
            approved = prov - timedelta(hours=rng.randint(4, 70))
            if p is excess:
                p.groups = p.groups + ["APP-ERP-GL-Approver"]
                self.plant("P3", "AC-01", p.sam, "New hire granted APP-ERP-GL-Approver, which was not on the approved request")
            if p is no_ticket:
                self.plant("P1", "AC-01", p.sam, "New hire account created with no access request ticket")
                continue
            if p is late_approval:
                approved = prov + timedelta(days=3, hours=2)
                self.plant("P2", "AC-01", p.sam, "Access request approved 3 days after the account was created")
            mgr = next(m for m in self.people if m.emp_id == p.manager_emp_id)
            self.access_requests.append({
                "ticket_id": self._ticket("AR"), "type": "new_hire", "employee_id": p.emp_id,
                "account": p.sam, "requested_groups": ";".join(sorted(requested)),
                "requested_by": "hr." + mgr.sam, "approver": mgr.sam, "approver_title": mgr.title,
                "approved_at": _iso(approved), "fulfilled_at": _iso(prov), "status": "Closed"})
        # transfers (movers)
        for mover in (self.mover_planted, self.mover_clean):
            mgr = next(m for m in self.people if m.emp_id == mover.manager_emp_id)
            done = _dt(add_business_days(mover.transfer_date, rng.randint(0, 2)), 15)
            self.transfer_tickets.append({
                "ticket_id": self._ticket("TRF"), "employee_id": mover.emp_id, "account": mover.sam,
                "from_department": mover.prior_dept, "to_department": mover.dept,
                "effective_date": _iso(mover.transfer_date),
                "groups_to_remove": ";".join(sorted(set(mover._old_groups) - set(mover.groups))),
                "groups_to_add": ";".join(sorted(set(mover.groups) - set(mover._old_groups))),
                "approver": mgr.sam, "completed_at": _iso(done), "status": "Closed"})
        retained = sorted(set(self.mover_planted._old_groups) - set(self.mover_planted.groups))
        self.mover_planted.groups = self.mover_planted.groups + retained
        self.plant("M1", "AC-01", self.mover_planted.sam,
                   f"Transferred employee kept prior-role access ({', '.join(retained)}) after transfer ticket closed")
        # terminations in period
        leavers = sorted([p for p in self.people if p.status == "terminated" and p.term_date >= PERIOD_START],
                         key=lambda p: p.term_date)
        self.leavers = leavers
        erp_active = rng.choice([p for p in leavers if p.erp_roles])
        still_enabled_used, still_enabled, late = rng.sample([p for p in leavers if p is not erp_active], 3)
        self.leaver_flags = {"enabled_used": still_enabled_used.sam, "enabled": still_enabled.sam,
                             "erp_active": erp_active.sam, "late": late.sam}
        for p in leavers:
            done = _dt(add_business_days(p.term_date, rng.choice([0, 0, 1])), rng.randint(9, 17))
            status = "Closed"
            if p is late:
                done = _dt(add_business_days(p.term_date, 9), 11)
                self.plant("D4", "AC-02", p.sam, "AD/ERP access removed 9 business days after termination")
            if p in (still_enabled_used, still_enabled):
                status = "Closed"   # ticket was closed but the account was never disabled
            self.termination_tickets.append({
                "ticket_id": self._ticket("TRM"), "employee_id": p.emp_id, "account": p.sam,
                "termination_date": _iso(p.term_date), "completed_at": _iso(done),
                "completed_by": "helpdesk", "status": status})
        self.plant("D1", "AC-02", still_enabled_used.sam,
                   "Terminated user still enabled in AD and logged on after termination date")
        self.plant("D2", "AC-02", still_enabled.sam, "Terminated user still enabled in AD")
        self.plant("D3", "AC-02", erp_active.sam, "Terminated user disabled in AD but still active in the ERP")
        self.term_completed = {t["account"]: t["completed_at"] for t in self.termination_tickets}

    def _build_ad_accounts(self) -> None:
        rng = self.rng
        asof = datetime.combine(PERIOD_END, time(18, 0))
        dormant = rng.sample([p for p in self.people if p.status == "active" and p.hire_date < PERIOD_START
                              and p.dept in ("Sales", "Operations", "Finance") and p.transfer_date is None
                              and p.title != "AP Manager"], 2)
        self.dormant = {p.sam for p in dormant}
        noexpire = rng.sample([p for p in self.people if p.status == "active" and p.dept in ("Sales", "Executive")], 2)
        devs = sorted(self.by_title("Software Developer"), key=lambda p: p.sam)
        self.rogue_dev = devs[0]
        helpdesk = self.by_title("Help Desk Technician")[0]
        for p in self.people:
            created = self.prov_dates.get(p.sam) or _dt(add_business_days(p.hire_date, -2), 10)
            uac_flags: list[str] = []
            enabled = True
            last_logon: datetime | None = asof - timedelta(days=rng.randint(0, 9), hours=rng.randint(0, 8))
            if p.status == "terminated":
                enabled = False
                last_logon = _dt(p.term_date, 16) - timedelta(days=rng.randint(0, 3))
                if p.sam == self.leaver_flags["enabled_used"]:
                    enabled = True
                    last_logon = _dt(p.term_date + timedelta(days=6), 21, 14)
                elif p.sam == self.leaver_flags["enabled"]:
                    enabled = True
            if p.status == "leave":
                last_logon = asof - timedelta(days=131)
            if p.sam in self.dormant:
                last_logon = asof - timedelta(days=rng.choice([118, 164]))
            if p.title == "Machinist":   # shared-shift workers log on less often
                shift_logon = asof - timedelta(days=rng.randint(0, 20))
                if p.status != "terminated":
                    last_logon = shift_logon
            if p in noexpire:
                uac_flags.append("DONT_EXPIRE_PASSWORD")
            if p is helpdesk:
                uac_flags.append("PASSWD_NOTREQD")
            ou = "OU=Users,OU=Kestrel" if enabled or p.status != "terminated" else "OU=Disabled Users,OU=Kestrel"
            groups = list(p.groups)
            if p.status == "terminated" and not enabled:
                groups = ["GG-AllStaff"]  # leavers' groups stripped when disabled
            self.ad_accounts.append({
                "sam": p.sam, "given": p.first, "sn": p.last, "display": p.display,
                "department": p.dept, "title": p.title, "employee_id": p.emp_id,
                "manager_emp_id": p.manager_emp_id, "ou": ou, "enabled": enabled,
                "uac_flags": uac_flags, "groups": sorted(set(groups)),
                "when_created": _iso(created), "last_logon": _iso(last_logon),
                "description": f"{p.title}, {p.dept}", "kind": "person",
                "password": _password(rng)})
        for p in self.dormant:
            self.plant("DM-" + p, "AC-06", p, "Enabled account with no logon in more than 90 days")
        on_leave = next(p for p in self.people if p.status == "leave")
        self.plant("DM-" + on_leave.sam, "AC-06", on_leave.sam,
                   "Account of employee on leave of absence not disabled after 90 days of inactivity")
        for p in noexpire:
            self.plant("PW3-" + p.sam, "AC-05", p.sam, "Non-service user account set to 'password never expires'")
        self.plant("PW4", "AC-05", helpdesk.sam, "User account flagged PASSWD_NOTREQD (password not required)")
        self.plant("PW1", "AC-05", "domain:minPwdLength", "Domain minimum password length 8 vs. standard 12")
        self.plant("PW2", "AC-05", "domain:lockoutThreshold", "Account lockout disabled (threshold 0) vs. standard 5")

        # Admin (tier-0) accounts for IT staff
        it_mgr = self.by_title("IT Manager")[0]
        sysadmins = self.by_title("Systems Administrator")
        self.it_mgr = it_mgr
        for p in [it_mgr, *sysadmins]:
            self.ad_accounts.append({
                "sam": f"adm-{p.sam}", "given": p.first, "sn": p.last, "display": f"{p.display} (admin)",
                "department": p.dept, "title": p.title, "employee_id": p.emp_id,
                "manager_emp_id": p.manager_emp_id, "ou": "OU=Admins,OU=Kestrel", "enabled": True,
                "uac_flags": [], "groups": ["Domain Admins"], "kind": "admin",
                "when_created": _iso(_dt(add_business_days(p.hire_date, 3), 11)),
                "last_logon": _iso(asof - timedelta(days=rng.randint(0, 6))),
                "description": f"Privileged admin account for {p.sam}", "password": _password(rng)})
            self.authorized_priv.append({"system": "Active Directory", "account": f"adm-{p.sam}",
                                         "privilege": "Domain Admins", "owner": p.sam,
                                         "business_justification": "Tier-0 administration",
                                         "approved_by": "CFO", "approved_on": "2025-09-15"})
        self.authorized_priv.append({"system": "Active Directory", "account": "Administrator",
                                     "privilege": "Domain Admins", "owner": it_mgr.sam,
                                     "business_justification": "Break-glass built-in account (vaulted)",
                                     "approved_by": "CFO", "approved_on": "2025-09-15"})
        # The developer with tier-0 rights (planted)
        self.ad_accounts = [dict(a, groups=sorted(set(a["groups"] + ["Domain Admins"])))
                            if a["sam"] == self.rogue_dev.sam else a for a in self.ad_accounts]
        self.plant("PR1", "AC-03", self.rogue_dev.sam, "Software developer's everyday account is a member of Domain Admins")

        # Service and generic accounts
        owner_left = next(p for p in self.leavers if p.title == "Software Developer")
        dba = self.by_title("Database Administrator")[0]
        svc = [
            ("svc_erp_app", "ERP application service", dba.sam, ["GG-ServiceAccounts"], 1, True),
            ("svc_backup", "Nightly backup agent", sysadmins[0].sam, ["GG-ServiceAccounts", "Backup Operators", "Domain Admins"], 0, True),
            ("svc_scan", "Network scanner/copier SMTP relay", None, ["GG-ServiceAccounts"], 2, False),
            ("svc_legacyftp", "Legacy EDI FTP bridge", owner_left.sam, ["GG-ServiceAccounts"], 412, True),
            ("svc_monitor", "Monitoring agent (read-only)", sysadmins[1].sam, ["GG-ServiceAccounts"], 0, True),
        ]
        for sam, purpose, owner, groups, days_idle, inventoried in svc:
            self.ad_accounts.append({
                "sam": sam, "given": "", "sn": "", "display": sam, "department": "Information Technology",
                "title": "Service Account", "employee_id": "", "manager_emp_id": None,
                "ou": "OU=Service Accounts,OU=Kestrel", "enabled": True, "uac_flags": ["DONT_EXPIRE_PASSWORD"],
                "groups": groups, "kind": "service",
                "when_created": _iso(_dt(date(2019, 3, 4) + timedelta(days=self.rng.randint(0, 900)), 10)),
                "last_logon": _iso(asof - timedelta(days=days_idle, hours=2)),
                "description": purpose, "password": _password(rng)})
            if inventoried:
                self.service_accounts.append({
                    "account": sam, "purpose": purpose, "owner": owner, "interactive_logon": "Denied",
                    "password_never_expires_exception": "Approved", "exception_approved_by": "IT Manager",
                    "last_reviewed": "2025-09-20"})
        self.plant("PR2", "AC-03", "svc_backup", "Backup service account is a member of Domain Admins")
        self.plant("SV2", "AC-07", "svc_scan", "Service account not in the service-account inventory (no owner)")
        self.plant("SV3", "AC-07", "svc_legacyftp", "Service account owner is a terminated employee")
        self.plant("DM-svc_legacyftp", "AC-06", "svc_legacyftp", "Service account inactive for 412 days but still enabled")
        self.ad_accounts.append({
            "sam": "frontdesk", "given": "Front", "sn": "Desk", "display": "Front Desk (shared)",
            "department": "Operations", "title": "Shared Account", "employee_id": "", "manager_emp_id": None,
            "ou": "OU=Shared,OU=Kestrel", "enabled": True, "uac_flags": ["DONT_EXPIRE_PASSWORD"],
            "groups": ["GG-AllStaff", "APP-ERP-Users"], "kind": "generic",
            "when_created": "2020-02-11T09:30:00", "last_logon": _iso(asof - timedelta(days=1)),
            "description": "Reception PC shared login", "password": _password(rng)})
        self.plant("SV1", "AC-07", "frontdesk", "Generic shared account enabled with ERP access")
        self.ad_accounts.append({
            "sam": "training01", "given": "Training", "sn": "01", "display": "Training 01",
            "department": "Human Resources", "title": "Shared Account", "employee_id": "", "manager_emp_id": None,
            "ou": "OU=Shared,OU=Kestrel", "enabled": False, "uac_flags": [], "groups": [], "kind": "generic",
            "when_created": "2021-05-03T09:30:00", "last_logon": "2023-03-01T10:00:00",
            "description": "Disabled training account", "password": _password(rng)})
        # Auditor's own read-only account (created at fieldwork; excluded from population by kind)
        self.ad_accounts.append({
            "sam": "svc_audit_ro", "given": "", "sn": "", "display": "External audit read-only",
            "department": "", "title": "Audit", "employee_id": "", "manager_emp_id": None,
            "ou": "OU=Service Accounts,OU=Kestrel", "enabled": True, "uac_flags": [], "groups": [],
            "kind": "audit", "when_created": "", "last_logon": "", "description": "Read-only account issued to the auditor for fieldwork",
            "password": "Lab-Audit-ReadOnly-2026!"})

    def _build_erp(self) -> None:
        rng = self.rng
        asof = datetime.combine(PERIOD_END, time(17, 0))
        ap_clerks = sorted(self.by_title("AP Clerk"), key=lambda p: p.sam)
        admin_clerk, sod_clerk = ap_clerks[0], ap_clerks[1]
        for p in self.people:
            if not p.erp_roles and p.sam != self.mover_planted.sam:
                continue
            roles = list(p.erp_roles)
            for g in p.groups:
                if g in ERP_GROUP_ROLES and ERP_GROUP_ROLES[g] not in roles:
                    roles.append(ERP_GROUP_ROLES[g])   # AD role groups drive ERP roles (nightly sync)
            if p is admin_clerk:
                roles.append("ERP_ADMIN")
            if p is sod_clerk:
                roles.append("AP_APPROVER")
            active = p.status != "terminated" or p.sam == self.leaver_flags["erp_active"] \
                or p.sam == self.leaver_flags["enabled_used"]
            deactivated = None
            if not active:
                deactivated = self.term_completed.get(p.sam) or _iso(_dt(p.term_date, 17))
            created = self.prov_dates.get(p.sam) or _dt(add_business_days(p.hire_date, -1), 13)
            last_login = asof - timedelta(days=rng.randint(0, 12))
            if p.status == "terminated":
                last_login = _dt(p.term_date, 15)
                if p.sam == self.leaver_flags["erp_active"]:
                    last_login = _dt(p.term_date, 15)
            self.erp_users.append({"username": p.sam, "full_name": p.display, "employee_id": p.emp_id,
                                   "is_active": active, "created_at": _iso(created),
                                   "deactivated_at": deactivated or "", "last_login_at": _iso(last_login),
                                   "roles": sorted(set(roles))})
        self.erp_users.append({"username": "erpadmin", "full_name": "ERP built-in administrator", "employee_id": "",
                               "is_active": True, "created_at": "2018-04-02T09:00:00", "deactivated_at": "",
                               "last_login_at": _iso(asof - timedelta(days=20)), "roles": ["ERP_ADMIN"]})
        self.erp_users.append({"username": "frontdesk", "full_name": "Front Desk (shared)", "employee_id": "",
                               "is_active": True, "created_at": "2020-02-11T10:00:00", "deactivated_at": "",
                               "last_login_at": _iso(asof - timedelta(days=1)), "roles": ["VIEWER"]})
        self.authorized_priv.append({"system": "ERP", "account": "erpadmin", "privilege": "ERP_ADMIN",
                                     "owner": self.it_mgr.sam, "business_justification": "Application administration (vaulted)",
                                     "approved_by": "CFO", "approved_on": "2025-09-15"})
        self.plant("PR4", "AC-03", admin_clerk.sam, "AP clerk holds the ERP_ADMIN role")
        self.plant("SOD1", "AC-03", sod_clerk.sam, "User can both enter vendor invoices (AP_CLERK) and approve payments (AP_APPROVER)")
        # Database roles
        dba = self.by_title("Database Administrator")[0]
        self.db_roles = [
            {"role": "erp_owner", "superuser": True, "login": True, "note": "bootstrap owner (vaulted)"},
            {"role": "erp_app", "superuser": False, "login": True, "note": "application connection"},
            {"role": "erp_report", "superuser": False, "login": True, "note": "read-only reporting"},
            {"role": dba.sam, "superuser": True, "login": True, "note": "DBA"},
            {"role": self.rogue_dev.sam, "superuser": True, "login": True, "note": "developer"},
            {"role": "svc_backup", "superuser": False, "login": True, "note": "backup (pg_read_all_data)"},
        ]
        for acct, owner, just in (("erp_owner", dba.sam, "Database owner / break-glass (vaulted)"),
                                  (dba.sam, dba.sam, "Database administrator")):
            self.authorized_priv.append({"system": "ERP database", "account": acct, "privilege": "SUPERUSER",
                                         "owner": owner, "business_justification": just,
                                         "approved_by": "CFO", "approved_on": "2025-09-15"})
        self.plant("PR3", "AC-03", self.rogue_dev.sam, "Software developer has SUPERUSER on the production ERP database")

    def _build_changes(self) -> None:
        rng = self.rng
        devs = sorted(self.by_title("Software Developer"), key=lambda p: p.sam)
        dev_mgr = self.by_title("Development Manager")[0]
        rel_mgr = self.by_title("Release Manager")[0]
        cab = [dev_mgr.sam, self.it_mgr.sam]
        # Release dates: roughly weekly-to-biweekly Tuesday/Thursday deployments
        d = PERIOD_START + timedelta(days=6)
        dates = []
        while d <= PERIOD_END:
            if d.weekday() in (1, 3):
                dates.append(d)
                d += timedelta(days=rng.choice([7, 9, 12, 14]))
            else:
                d += timedelta(days=1)
        emergency_idx = set(rng.sample(range(len(dates)), 4))
        normal_idx = [i for i in range(len(dates)) if i not in emergency_idx]
        no_ticket = set(rng.sample(normal_idx, 2))
        rest = [i for i in normal_idx if i not in no_ticket]
        late_appr, no_test = rng.sample(rest, 2)
        self_deploy = set(rng.sample([i for i in range(len(dates)) if i not in no_ticket], 3))
        rng.choice(sorted(emergency_idx))  # see CM-03 note below
        migration_no = 1
        for i, rd in enumerate(dates):
            emergency = i in emergency_idx
            deployed = _dt(rd, 19 if not emergency else rng.randint(10, 22), rng.randint(0, 59))
            author = rng.choice(devs)
            deployer = rel_mgr
            if i in self_deploy:
                author = self.rogue_dev
                deployer = self.rogue_dev
            tag = f"rel-{rd.isoformat()}" + ("-hotfix" if emergency else "")
            migrations = []
            if rng.random() < 0.35:
                migrations.append(f"V{migration_no:03d}")
                migration_no += 1
            chg = None if i in no_ticket else self._ticket("CHG")
            rel = {"tag": tag, "date": rd, "deployed_at": deployed, "author": author, "deployer": deployer,
                   "emergency": emergency, "change_id": chg, "migrations": migrations,
                   "n_commits": rng.randint(1, 4)}
            self.releases.append(rel)
            if chg is None:
                self.plant(f"C1-{tag}", "CM-01", tag, "Production release with no change ticket")
                continue
            approver = rng.choice(cab)
            approved = deployed - timedelta(days=rng.randint(1, 6), hours=rng.randint(1, 5))
            tested = "UAT sign-off attached; regression suite passed"
            uat_by = rng.choice(self.by_title("Controller") + self.by_title("AP Manager") + self.by_title("Sales Manager")).sam
            if emergency:
                approved = _dt(add_business_days(rd, rng.choice([1, 1, 2])), 10)
                tested = "Smoke test in production (emergency)"
                # the late-emergency draw above is still made (keeps the RNG stream stable) but no issue is planted:
                # CM-03 is one of the controls deliberately left clean so the lab has effective controls too.
            if i == late_appr:
                approved = deployed + timedelta(days=2, hours=3)
                self.plant(f"C2-{tag}", "CM-01", tag, "Change approved two days after it was deployed")
            if i == no_test:
                tested, uat_by = "", ""
                self.plant(f"C3-{tag}", "CM-01", tag, "No testing / UAT evidence on the change ticket")
            if i in self_deploy:
                self.plant(f"SOD-{tag}", "CM-02", tag, "Developer deployed their own change to production")
            self.change_tickets.append({
                "change_id": chg, "type": "Emergency" if emergency else "Normal",
                "summary": rng.choice(["Order entry validation fix", "Pricing table update", "Invoice export format",
                                       "Customer portal performance", "Credit-limit check", "Shipping label API",
                                       "GL interface mapping", "Tax rate table", "Report filter bug",
                                       "Session timeout setting"]),
                "release_tag": tag, "requested_by": rng.choice(self.by_title("Sales Manager") + self.by_title("Controller")).sam,
                "developer": author.sam, "approver": approver, "approved_at": _iso(approved),
                "test_evidence": tested, "uat_signoff_by": uat_by, "scheduled_for": _iso(rd),
                "implemented_by": deployer.sam, "status": "Closed"})
            for v in migrations:
                self.migrations_applied.append({"version": v, "applied_at": _iso(deployed + timedelta(minutes=3)),
                                                "applied_by": "erp_owner", "release_tag": tag})
        # A database change applied directly in production, outside any release (planted)
        direct = {"version": f"V{migration_no:03d}", "applied_at": "2026-05-14T22:41:07",
                  "applied_by": self.rogue_dev.sam, "release_tag": ""}
        self.migrations_applied.append(direct)
        self.plant("DB1", "CM-04", direct["version"], "Schema change applied directly to production outside the release process")

    def _build_uar(self) -> None:
        quarters = [("FY26-Q1", date(2025, 12, 31)), ("FY26-Q2", date(2026, 3, 31)),
                    ("FY26-Q3", date(2026, 6, 30)), ("FY26-Q4", date(2026, 9, 30))]
        controller = self.by_title("Controller")[0]
        target = sorted(self.by_title("AP Manager"), key=lambda p: p.sam)[0]
        n_erp = sum(1 for u in self.erp_users if u["is_active"])
        n_priv = sum(1 for a in self.ad_accounts if "Domain Admins" in a["groups"]) + 1
        for q, qe in quarters:
            for system, reviewer in (("ERP", controller.sam), ("AD privileged groups", "cfo")):
                signoff = add_business_days(qe, self.rng.randint(8, 16))
                reviewer_sam = reviewer if reviewer != "cfo" else self.by_title("Chief Financial Officer")[0].sam
                removals = 0
                if q == "FY26-Q2" and system == "ERP":
                    signoff = qe + timedelta(days=41)
                    self.plant("U1", "AC-04", f"{q}-ERP", "ERP access review signed off 41 days after quarter end (standard: 30)")
                if q == "FY26-Q3" and system == "AD privileged groups":
                    reviewer_sam = self.it_mgr.sam
                    self.plant("U3", "AC-04", f"{q}-ADPRIV",
                               "IT Manager reviewed privileged groups that include his own admin account")
                if q == "FY26-Q4" and system == "ERP":
                    removals = 1
                    self.uar_detail.append({"review_id": f"{q}-ERP", "account": target.sam,
                                            "entitlement": "APP-ERP-AP-Approver", "decision": "Remove",
                                            "reviewer": reviewer_sam,
                                            "comment": "Duplicate approver; Controller covers AP approvals",
                                            "removal_ticket": "AR-REMOVE-0412", "removal_status": "Closed"})
                    self.plant("U2", "AC-04", f"{q}-ERP",
                               "Access-review removal (APP-ERP-AP-Approver) marked complete but still present in AD")
                self.uar_signoffs.append({"review_id": f"{q}-{'ERP' if system == 'ERP' else 'ADPRIV'}",
                                          "quarter": q, "quarter_end": _iso(qe), "system": system,
                                          "reviewer": reviewer_sam, "signed_off_on": _iso(signoff),
                                          "accounts_reviewed": n_erp if system == "ERP" else n_priv,
                                          "removals_requested": removals})

    def _build_operations(self) -> None:
        rng = self.rng
        sysadmin = self.by_title("Systems Administrator")[0].sam
        days = [PERIOD_START + timedelta(days=i) for i in range((PERIOD_END - PERIOD_START).days + 1)]
        fail_days = set(rng.sample(days[20:-20], 6))
        streak_start = rng.choice(days[60:-60])
        fail_days |= {streak_start + timedelta(days=k) for k in range(3)}
        fail_sorted = sorted(fail_days)
        unticketed = set(rng.sample([d for d in fail_sorted if not streak_start <= d <= streak_start + timedelta(days=2)], 2))
        for d in days:
            start = _dt(d, 1, 0) + timedelta(minutes=rng.randint(0, 9))
            ok = d not in fail_days
            dur = rng.randint(38, 55)
            ticket = ""
            if not ok and d not in unticketed:
                ticket = self._ticket("INC")
                self.incidents.append(self._incident(ticket, _dt(d, 7, 30), "P3", "Backup",
                                                     "Nightly ERP backup failed - storage target unreachable",
                                                     resolve_days=1))
            self.backup_log.append({"job": "ERP-DB-NIGHTLY", "run_date": _iso(d), "start": _iso(start),
                                    "end": _iso(start + timedelta(minutes=dur if ok else 3)),
                                    "status": "Success" if ok else "Failed",
                                    "size_gb": round(rng.uniform(41.0, 47.5), 1) if ok else 0.0,
                                    "ticket": ticket})
        for d in sorted(unticketed):
            self.plant(f"BK-{d.isoformat()}", "OPS-01", d.isoformat(), "Backup failure with no incident ticket / follow-up")
        # Restore testing: last test predates the period
        self.restore_tests.append({"test_id": "RT-2024-01", "date": "2024-11-14", "system": "ERP database",
                                   "result": "Successful", "performed_by": sysadmin,
                                   "notes": "Restored to DR host; row counts agreed"})
        self.plant("RT1", "OPS-02", "management restore test (FY2026)", "No restore test performed during the audit period (annual requirement)")
        # Batch interface: ERP -> GL, every business day
        bdays = [d for d in days if is_business_day(d)]
        b_fail = sorted(rng.sample(bdays, 6))
        rng.choice(b_fail)  # drawn for RNG stability; OPS-03 deliberately left clean
        for d in bdays:
            ok = d not in b_fail
            ticket = rerun = ""
            if not ok:
                ticket = self._ticket("INC")
                rerun = "Success"
                self.incidents.append(self._incident(ticket, _dt(d, 6, 45), "P2", "Batch job",
                                                     "ERP-GL interface failed - lock timeout", resolve_days=0))
            self.batch_log.append({"job": "ERP-GL-INTERFACE", "run_date": _iso(d),
                                   "status": "Success" if ok else "Failed", "records": rng.randint(180, 900) if ok else 0,
                                   "rerun_status": rerun, "ticket": ticket})
        # Other incidents during the year, including three P1s
        cats = ["Network", "Email", "ERP", "Hardware", "Access", "Printing"]
        for _ in range(22):
            opened = _dt(_rand_date(rng, PERIOD_START, PERIOD_END), rng.randint(7, 18), rng.randint(0, 59))
            self.incidents.append(self._incident(self._ticket("INC"), opened, rng.choice(["P3", "P3", "P4", "P2"]),
                                                 rng.choice(cats), "User-reported issue", resolve_days=rng.randint(0, 4)))
        p1_dates = sorted(_rand_date(rng, PERIOD_START, PERIOD_END) for _ in range(3))
        rng.randrange(3)  # drawn for RNG stability; OPS-04 deliberately left clean (every P1 has an RCA)
        for k, d in enumerate(p1_dates):
            t = self._ticket("INC")
            inc = self._incident(t, _dt(d, 8, 5), "P1", "ERP", "ERP outage - order entry unavailable", resolve_days=0)
            inc["rca_reference"] = f"PRB-{2600 + k}"
            inc["rca_completed_on"] = _iso(add_business_days(d, rng.randint(3, 8)))
            self.incidents.append(inc)
        self.incidents.sort(key=lambda r: r["opened_at"])

    def _incident(self, ticket: str, opened: datetime, prio: str, cat: str, summary: str, resolve_days: int) -> dict:
        resolved = _dt(add_business_days(opened.date(), resolve_days), min(opened.hour + 3, 22), opened.minute)
        return {"incident_id": ticket, "opened_at": _iso(opened), "priority": prio, "category": cat,
                "summary": summary, "resolved_at": _iso(resolved), "status": "Closed",
                "rca_reference": "", "rca_completed_on": ""}

    # ------------------------------------------------------------------ outputs
    def hr_roster(self) -> list[dict]:
        rows = []
        for p in sorted(self.people, key=lambda x: x.emp_id):
            rows.append({"employee_id": p.emp_id, "first_name": p.first, "last_name": p.last,
                         "network_id": p.sam, "department": p.dept, "title": p.title,
                         "manager_employee_id": p.manager_emp_id or "", "hire_date": _iso(p.hire_date),
                         "employment_status": {"active": "Active", "terminated": "Terminated", "leave": "Leave of absence"}[p.status],
                         "termination_date": _iso(p.term_date), "prior_department": p.prior_dept or "",
                         "transfer_date": _iso(p.transfer_date)})
        return rows

    def write(self, root: Path) -> dict[str, int]:
        build = root / "lab" / ".build"
        pbc = root / "audit" / "pbc"
        build.mkdir(parents=True, exist_ok=True)
        pbc.mkdir(parents=True, exist_ok=True)
        emp_to_sam = {p.emp_id: p.sam for p in self.people}
        ad_spec = {"realm_dn": REALM_DN, "company": COMPANY, "mail_domain": MAIL_DOMAIN,
                   "password_policy": {"min_pwd_length": 8, "complexity": "on", "history_length": 24,
                                       "min_pwd_age": 1, "max_pwd_age": 90, "lockout_threshold": 0,
                                       "lockout_duration": 30, "reset_lockout_after": 30},
                   "groups": GROUP_DESCRIPTIONS | {g: f"{d} department" for d, g in DEPT_GROUP.items()},
                   "accounts": [dict(a, manager_sam=emp_to_sam.get(a["manager_emp_id"])) for a in self.ad_accounts]}
        (build / "ad_spec.json").write_text(json.dumps(ad_spec, indent=1, default=str), encoding="utf-8", newline="\n")
        (build / "erp_seed.sql").write_text(self.erp_sql(), encoding="utf-8", newline="\n")
        releases = [dict(r, date=r["date"].isoformat(), deployed_at=_iso(r["deployed_at"]),
                         author=asdict_min(r["author"]), deployer=asdict_min(r["deployer"]))
                    for r in self.releases]
        (build / "releases.json").write_text(json.dumps(releases, indent=1), encoding="utf-8", newline="\n")
        files = {
            "hr_roster.csv": self.hr_roster(),
            "access_requests.csv": self.access_requests,
            "transfer_tickets.csv": self.transfer_tickets,
            "termination_tickets.csv": self.termination_tickets,
            "authorized_privileged_access.csv": self.authorized_priv,
            "service_account_inventory.csv": self.service_accounts,
            "uar_signoffs.csv": self.uar_signoffs,
            "uar_detail.csv": self.uar_detail,
            "change_tickets.csv": self.change_tickets,
            "backup_job_log.csv": self.backup_log,
            "restore_test_log.csv": self.restore_tests,
            "batch_job_log.csv": self.batch_log,
            "incidents.csv": self.incidents,
        }
        counts = {}
        for name, rows in files.items():
            write_csv(pbc / name, rows)
            counts[name] = len(rows)
        key_path = root / "lab" / "seed" / "answer_key.json"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(json.dumps({"seed": SEED, "note": "Planted issues. NOT read by any control test; "
                                        "used only to score detection after the audit.",
                                        "issues": self.answer_key}, indent=1), encoding="utf-8", newline="\n")
        counts["answer_key"] = len(self.answer_key)
        return counts

    def erp_sql(self) -> str:
        rng = random.Random(SEED + 1)
        q = lambda s: "'" + str(s).replace("'", "''") + "'"  # noqa: E731
        out = ["-- Generated by itgc.scenario - fictional ERP for Kestrel Valve Co.",
               "CREATE SCHEMA IF NOT EXISTS app;",
               "CREATE TABLE app.users (username text PRIMARY KEY, full_name text, employee_id text, is_active boolean NOT NULL,"
               " created_at timestamp, deactivated_at timestamp, last_login_at timestamp);",
               "CREATE TABLE app.user_roles (username text REFERENCES app.users, role text, PRIMARY KEY (username, role));",
               "CREATE TABLE app.vendors (vendor_id serial PRIMARY KEY, name text, created_by text, created_at timestamp);",
               "CREATE TABLE app.invoices (invoice_id serial PRIMARY KEY, vendor_id int REFERENCES app.vendors, amount numeric(12,2),"
               " entered_by text, approved_by text, entered_at timestamp);",
               "CREATE TABLE app.gl_journal (je_id serial PRIMARY KEY, period text, account text, debit numeric(14,2),"
               " credit numeric(14,2), posted_by text, approved_by text);",
               "CREATE TABLE public.schema_migrations (version text PRIMARY KEY, applied_at timestamp, applied_by text);"]
        for u in self.erp_users:
            out.append(f"INSERT INTO app.users VALUES ({q(u['username'])},{q(u['full_name'])},{q(u['employee_id'])},"
                       f"{'true' if u['is_active'] else 'false'},{q(u['created_at'])},"
                       f"{q(u['deactivated_at']) if u['deactivated_at'] else 'NULL'},{q(u['last_login_at'])});")
            for r in u["roles"]:
                out.append(f"INSERT INTO app.user_roles VALUES ({q(u['username'])},{q(r)});")
        clerks = [u["username"] for u in self.erp_users if "AP_CLERK" in u["roles"]] or ["erpadmin"]
        approvers = [u["username"] for u in self.erp_users if "AP_APPROVER" in u["roles"]] or ["erpadmin"]
        for v in range(1, 61):
            out.append(f"INSERT INTO app.vendors (name, created_by, created_at) VALUES ("
                       f"{q('Vendor ' + str(v).zfill(3))},{q(rng.choice(clerks))},'2025-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}');")
        for _ in range(1500):
            out.append(f"INSERT INTO app.invoices (vendor_id, amount, entered_by, approved_by, entered_at) VALUES ("
                       f"{rng.randint(1, 60)},{rng.randint(1500, 2_500_000) / 100:.2f},{q(rng.choice(clerks))},"
                       f"{q(rng.choice(approvers))},'2026-{rng.randint(1, 9):02d}-{rng.randint(1, 28):02d}');")
        for i in range(1200):
            amt = rng.randint(100, 900_000) / 100
            out.append(f"INSERT INTO app.gl_journal (period, account, debit, credit, posted_by, approved_by) VALUES ("
                       f"'FY26-P{(i % 12) + 1:02d}','{rng.choice(['1000', '1200', '2000', '4000', '5000', '6100'])}',"
                       f"{amt:.2f},{amt:.2f},'gl','controller');")
        for m in self.migrations_applied:
            out.append(f"INSERT INTO public.schema_migrations VALUES ({q(m['version'])},{q(m['applied_at'])},{q(m['applied_by'])});")
        for r in self.db_roles:
            if r["role"] == "erp_owner":
                continue
            attrs = "LOGIN" + (" SUPERUSER" if r["superuser"] else "")
            out.append(f"CREATE ROLE \"{r['role']}\" {attrs} PASSWORD 'lab-only-{r['role']}';")
            out.append(f"COMMENT ON ROLE \"{r['role']}\" IS {q(r['note'])};")
        out += ["GRANT USAGE ON SCHEMA app TO erp_app, erp_report;",
                "GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO erp_app;",
                "GRANT SELECT ON ALL TABLES IN SCHEMA app TO erp_report;",
                "GRANT pg_read_all_data TO svc_backup;",
                # the auditor's read-only login (needs to read pg_roles + app.* + schema_migrations)
                "CREATE ROLE audit_ro LOGIN PASSWORD 'lab-only-audit-ro';",
                "GRANT pg_read_all_data TO audit_ro;"]
        return "\n".join(out) + "\n"


def asdict_min(p: Person) -> dict:
    return {"sam": p.sam, "name": p.display, "email": f"{p.sam}@{MAIL_DOMAIN}"}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def generate(root: Path, seed: int = SEED) -> dict[str, int]:
    return Scenario(seed).build().write(root)


__all__ = ["Scenario", "generate", "Person", "asdict"]
