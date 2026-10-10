"""Load the generated directory spec into the Samba AD DC.

Runs INSIDE the domain-controller container (uses Samba's own Python bindings against the
local sam.ldb), i.e. this plays the role of "the company's admins built the domain over the
years". Time-based attributes (whenCreated, lastLogonTimestamp) are back-dated with the LDB
"relax" control so the directory looks like it has a 12-month history; this is only possible
because the seeder has root on the DC and is documented as a lab limitation.

Usage (inside container): python3 seed_dc.py /tmp/ad_spec.json
"""
import json
import subprocess
import sys
from datetime import UTC, datetime

import ldb
from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB

UF_ACCOUNTDISABLE = 0x2
UF_PASSWD_NOTREQD = 0x20
UF_NORMAL_ACCOUNT = 0x200
UF_DONT_EXPIRE_PASSWD = 0x10000
FLAGS = {"PASSWD_NOTREQD": UF_PASSWD_NOTREQD, "DONT_EXPIRE_PASSWORD": UF_DONT_EXPIRE_PASSWD}
EPOCH_1601 = datetime(1601, 1, 1, tzinfo=UTC)
OUS = ["OU=Kestrel", "OU=Users,OU=Kestrel", "OU=Admins,OU=Kestrel", "OU=Service Accounts,OU=Kestrel",
       "OU=Groups,OU=Kestrel", "OU=Disabled Users,OU=Kestrel", "OU=Shared,OU=Kestrel"]


def filetime(iso):
    dt = datetime.fromisoformat(iso).replace(tzinfo=UTC)
    return str(int((dt - EPOCH_1601).total_seconds() * 10_000_000))


def gentime(iso):
    return datetime.fromisoformat(iso).strftime("%Y%m%d%H%M%S.0Z")


def tool(*args):
    subprocess.run(["samba-tool", *args], check=True, stdout=subprocess.DEVNULL)


def replace(samdb, dn, attrs, controls=None):
    msg = ldb.Message()
    msg.dn = ldb.Dn(samdb, dn)
    for k, v in attrs.items():
        msg[k] = ldb.MessageElement(str(v), ldb.FLAG_MOD_REPLACE, k)
    samdb.modify(msg, controls=controls or [])


def main(path):
    spec = json.load(open(path, encoding="utf-8"))
    pp = spec["password_policy"]
    tool("domain", "passwordsettings", "set", f"--complexity={pp['complexity']}",
         f"--history-length={pp['history_length']}", f"--min-pwd-age={pp['min_pwd_age']}",
         f"--max-pwd-age={pp['max_pwd_age']}", f"--min-pwd-length={pp['min_pwd_length']}",
         f"--account-lockout-threshold={pp['lockout_threshold']}",
         f"--account-lockout-duration={pp['lockout_duration']}",
         f"--reset-account-lockout-after={pp['reset_lockout_after']}")

    lp = LoadParm()
    lp.load_default()
    samdb = SamDB(url="/var/lib/samba/private/sam.ldb", session_info=system_session(), lp=lp)
    base = str(samdb.domain_dn())
    for ou in OUS:
        samdb.create_ou(f"{ou},{base}")
    for name, desc in spec["groups"].items():
        samdb.newgroup(name, groupou="OU=Groups,OU=Kestrel", description=desc)

    dns = {}
    for a in spec["accounts"]:
        person = a["kind"] in ("person",)
        samdb.newuser(
            a["sam"], a["password"], userou=a["ou"], useusernameascn=not person,
            givenname=a["given"] or None, surname=a["sn"] or None,
            jobtitle=a["title"] or None, department=a["department"] or None,
            company=spec["company"], description=a["description"] or None,
            mailaddress=f"{a['sam']}@{spec['mail_domain']}" if person else None)
        res = samdb.search(base=base, expression=f"(sAMAccountName={ldb.binary_encode(a['sam'])})", attrs=["dn"])
        dns[a["sam"]] = str(res[0].dn)
        extra = {"displayName": a["display"]}
        if a["employee_id"]:
            extra["employeeID"] = a["employee_id"]
        replace(samdb, dns[a["sam"]], extra)

    for a in spec["accounts"]:
        dn = dns[a["sam"]]
        if a.get("manager_sam") and a["manager_sam"] in dns:
            replace(samdb, dn, {"manager": dns[a["manager_sam"]]})
        uac = UF_NORMAL_ACCOUNT
        for f in a["uac_flags"]:
            uac |= FLAGS[f]
        if not a["enabled"]:
            uac |= UF_ACCOUNTDISABLE
        replace(samdb, dn, {"userAccountControl": uac})
        for g in a["groups"]:
            samdb.add_remove_group_members(g, [a["sam"]], add_members_operation=True)
        backdate = {}
        if a["when_created"]:
            backdate["whenCreated"] = gentime(a["when_created"])
        if a["last_logon"]:
            backdate["lastLogonTimestamp"] = filetime(a["last_logon"])
        if backdate:
            replace(samdb, dn, backdate, controls=["relax:0"])

    # Fine-grained password policy for service accounts (a well-designed control in the lab)
    tool("domain", "passwordsettings", "pso", "create", "PSO-ServiceAccounts", "10",
         "--min-pwd-length=20", "--complexity=on", "--max-pwd-age=365", "--history-length=24",
         "--account-lockout-threshold=0")
    tool("domain", "passwordsettings", "pso", "apply", "PSO-ServiceAccounts", "GG-ServiceAccounts")
    print(f"seeded {len(spec['accounts'])} accounts, {len(spec['groups'])} groups")


if __name__ == "__main__":
    main(sys.argv[1])
