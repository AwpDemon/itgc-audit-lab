"""The PowerShell collector (collectors/Get-ADEvidence.ps1) was run against the same lab DC as
the Python collector. Its saved output must agree field-by-field with the Python evidence."""
import json
from pathlib import Path

from .conftest import BASELINE

FIELDS = ["enabled", "uac", "uac_flags", "when_created", "member_of", "employee_id", "ou", "manager", "title", "department"]


def test_powershell_and_python_collectors_agree():
    fixture = Path(__file__).parent / "fixtures" / "ad_users_powershell_baseline.json"
    ps = json.loads(fixture.read_text(encoding="utf-8-sig"))
    py = {u["sam"]: u for u in json.loads((BASELINE / "system" / "ad_users.json").read_text(encoding="utf-8"))}
    assert len(ps) == len(py) == 95
    for u in ps:
        p = py[u["sam"]]
        for f in FIELDS:
            a, b = u[f], p[f]
            if isinstance(a, list) or isinstance(b, list):
                a, b = sorted(a or []), sorted(b or [])
            assert a == b, (u["sam"], f)
        if u["sam"] != "svc_audit_ro":       # the auditor's own logon moves between runs
            assert (u["last_logon_timestamp"] or "")[:19] == (p["last_logon_timestamp"] or "")[:19]
