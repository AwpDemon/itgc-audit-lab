"""Edge cases with tiny hand-built evidence (no lab needed)."""
from pathlib import Path

import yaml

from itgc.controls.access import test_ac02 as run_ac02
from itgc.controls.access import test_ac05 as run_ac05
from itgc.controls.access import test_ac06 as run_ac06
from itgc.controls.access import test_ac07 as run_ac07
from itgc.controls.base import account_kind
from itgc.controls.change import test_cm02 as run_cm02
from itgc.controls.change import test_cm04 as run_cm04
from itgc.evidence import Evidence

STD = yaml.safe_load((Path(__file__).resolve().parents[1] / "audit/pbc/it_security_standard.yaml").read_text(encoding="utf-8"))


def user(sam, enabled=True, flags=("NORMAL_ACCOUNT",), emp="E1", ou="OU=Users,OU=Kestrel", last=None,
         created="2020-01-01T00:00:00+00:00", groups=()):
    return {"sam": sam, "enabled": enabled, "uac_flags": list(flags), "employee_id": emp, "ou": ou,
            "last_logon_timestamp": last, "when_created": created, "member_of": list(groups), "description": ""}


def ev(**kw):
    e = Evidence(root=Path("."), standard=STD)
    for k, v in kw.items():
        setattr(e, k, v)
    return e


def test_account_kinds():
    assert account_kind(user("Administrator")) == "builtin"
    assert account_kind(user("svc_x", ou="OU=Service Accounts,OU=Kestrel", emp=None)) == "service"
    assert account_kind(user("adm-bob", ou="OU=Admins,OU=Kestrel")) == "admin"
    assert account_kind(user("kiosk", emp=None)) == "generic"
    assert account_kind(user("svc_audit_ro", emp=None)) == "auditor"


def test_ac02_deleted_account_counts_as_removed_and_late_ticket_fails():
    hr = [{"employee_id": "E9", "network_id": "gone", "employment_status": "Terminated", "termination_date": "2026-03-02"}]
    tickets = [{"account": "gone", "ticket_id": "T1", "completed_at": "2026-03-06T10:00:00"}]
    res = run_ac02(ev(users=[], erp_users=[], pbc={"hr_roster": hr, "termination_tickets": tickets}))
    row = res.rows[0]
    assert row.attrs["A"] == "Pass" and row.attrs["B"] == "Pass" and row.attrs["C"] == "Exception"   # 4 business days


def test_ac05_service_exception_must_be_approved():
    users = [user("svc_ok", flags=("NORMAL_ACCOUNT", "DONT_EXPIRE_PASSWORD"), emp=None, ou="OU=Service Accounts"),
             user("svc_bad", flags=("NORMAL_ACCOUNT", "DONT_EXPIRE_PASSWORD"), emp=None, ou="OU=Service Accounts"),
             user("bob", flags=("NORMAL_ACCOUNT", "PASSWD_NOTREQD")),
             user("old", enabled=False, flags=("ACCOUNTDISABLE", "PASSWD_NOTREQD"))]
    inv = [{"account": "svc_ok", "owner": "x", "password_never_expires_exception": "Approved"}]
    policy = {"min_pwd_length": 14, "complexity_enabled": True, "history_length": 24, "max_pwd_age_days": 60,
              "min_pwd_age_days": 1, "lockout_threshold": 5, "lockout_duration_minutes": 30}
    res = run_ac05(ev(users=users, policy=policy, pbc={"service_account_inventory": inv}))
    assert set(res.exception_items()) == {"svc_bad", "bob"}       # disabled accounts ignored


def test_ac06_dormancy_uses_period_end_and_replication_tolerance():
    users = [user("a", last="2026-06-20T00:00:00+00:00"),   # 102 days before 30 Sep -> within 90+14
             user("b", last="2026-06-10T00:00:00+00:00"),   # 112 days -> exception
             user("c", last=None, created="2026-10-05T00:00:00+00:00")]   # created after period end
    assert run_ac06(ev(users=users)).exception_items() == ["b"]


def test_ac07_owner_must_be_active():
    users = [user("svc_a", emp=None, ou="OU=Service Accounts"), user("shared", emp=None)]
    hr = [{"network_id": "left", "employment_status": "Terminated"}]
    inv = [{"account": "svc_a", "owner": "left"}]
    res = run_ac07(ev(users=users, pbc={"service_account_inventory": inv, "hr_roster": hr}))
    assert set(res.exception_items()) == {"svc_a", "shared"}


def test_cm02_and_cm04():
    tags = [{"tag": "r1", "commits": [{"author_email": "dev@x"}], "migrations": ["V001__a.sql"]}]
    deploys = [{"tag": "r1", "deployed_by": "dev", "deployed_at": "2026-01-01T19:00:00"}]
    res = run_cm02(ev(tags=tags, deploy_log=deploys, priv_groups={"PRD-Deployers": ["rel"]}))
    assert res.rows[0].attrs == {"A": "Exception", "B": "Exception"}
    migs = [{"version": "V001", "applied_at": "2026-01-01T19:03:00", "applied_by": "erp_owner"},
            {"version": "V002", "applied_at": "2026-02-01T22:00:00", "applied_by": "dev"}]
    assert run_cm04(ev(tags=tags, deploy_log=deploys, migrations=migs)).exception_items() == ["V002"]
