"""Collect Active Directory evidence over LDAPS with a read-only account (python ldap3).

Evidence produced (all JSON):
* ad_users.json           - every user object with lifecycle-relevant attributes
* ad_privileged_groups.json - recursive membership of privileged + key application groups
* ad_domain_policy.json   - default domain password/lockout policy and any readable PSOs

Only standard LDAP reads are used; the same queries work against Windows Server AD.
"""
from __future__ import annotations

import ssl
from dataclasses import dataclass
from datetime import UTC

from ..ad import PRIVILEGED_AD_GROUPS, cn_of, decode_uac, interval_to_days, interval_to_minutes, is_enabled, ou_path
from ..dates import from_filetime

USER_ATTRS = ["sAMAccountName", "displayName", "givenName", "sn", "employeeID", "department", "title",
              "manager", "description", "userAccountControl", "whenCreated", "lastLogonTimestamp",
              "pwdLastSet", "accountExpires", "memberOf", "objectSid", "userPrincipalName"]
POLICY_ATTRS = ["minPwdLength", "pwdProperties", "pwdHistoryLength", "maxPwdAge", "minPwdAge",
                "lockoutThreshold", "lockoutDuration", "lockOutObservationWindow"]
PSO_ATTRS = ["cn", "msDS-PasswordSettingsPrecedence", "msDS-MinimumPasswordLength", "msDS-PasswordComplexityEnabled",
             "msDS-MaximumPasswordAge", "msDS-LockoutThreshold", "msDS-PSOAppliesTo"]
APP_GROUPS = ["APP-ERP-AP-Clerk", "APP-ERP-AP-Approver", "APP-ERP-GL-Poster", "APP-ERP-GL-Approver",
              "PRD-Deployers", "DBA-Admins", "DEV-Developers"]
IN_CHAIN = "1.2.840.113556.1.4.1941"   # LDAP_MATCHING_RULE_IN_CHAIN (recursive group membership)


@dataclass
class LdapTarget:
    host: str
    port: int
    user: str
    password: str
    base_dn: str
    ca_file: str | None = None
    tls_name: str | None = None


def first(attrs: dict, name: str) -> str | None:
    """First value of a multi-valued LDAP attribute dict ({name: [str, ...]})."""
    v = attrs.get(name)
    if v in (None, [], ""):
        return None
    if isinstance(v, (list, tuple)):
        v = v[0]
    return v.decode() if isinstance(v, bytes) else str(v)


def gen_time(value: str | None) -> str | None:
    """LDAP GeneralizedTime '20240611100000.0Z' -> ISO 8601 UTC."""
    if not value:
        return None
    from datetime import datetime
    return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC).isoformat()


def connect(t: LdapTarget):
    from ldap3 import Connection, Server, Tls

    if t.ca_file:
        tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=t.ca_file, valid_names=[t.tls_name] if t.tls_name else None)
    else:
        tls = Tls(validate=ssl.CERT_NONE)
    server = Server(t.host, port=t.port, use_ssl=True, tls=tls, get_info=None, connect_timeout=10)
    return Connection(server, user=t.user, password=t.password, auto_bind=True, read_only=True, raise_exceptions=True)


def normalize_user(dn: str, attrs: dict) -> dict:
    """Map raw LDAP attributes ({name: [values]}) to the evidence schema.

    Kept free of ldap3 types so unit tests can feed fixture dicts.
    """
    uac = int(first(attrs, "userAccountControl") or 0)
    last = from_filetime(first(attrs, "lastLogonTimestamp"))
    pls = from_filetime(first(attrs, "pwdLastSet"))
    manager = first(attrs, "manager")
    return {
        "sam": first(attrs, "sAMAccountName"),
        "dn": dn,
        "ou": ou_path(dn),
        "display_name": first(attrs, "displayName"),
        "employee_id": first(attrs, "employeeID"),
        "department": first(attrs, "department"),
        "title": first(attrs, "title"),
        "manager": cn_of(manager) if manager else None,
        "description": first(attrs, "description"),
        "uac": uac,
        "uac_flags": decode_uac(uac),
        "enabled": is_enabled(uac),
        "when_created": gen_time(first(attrs, "whenCreated")),
        "last_logon_timestamp": last.isoformat() if last else None,
        "pwd_last_set": pls.isoformat() if pls else None,
        "member_of": sorted(cn_of(str(g)) for g in (attrs.get("memberOf") or [])),
    }


def normalize_policy(d: dict) -> dict:
    def i(name):
        v = first(d, name)
        return int(v) if v is not None else None
    return {
        "min_pwd_length": i("minPwdLength"),
        "complexity_enabled": bool((i("pwdProperties") or 0) & 1),
        "history_length": i("pwdHistoryLength"),
        "max_pwd_age_days": interval_to_days(i("maxPwdAge")),
        "min_pwd_age_days": interval_to_days(i("minPwdAge")),
        "lockout_threshold": i("lockoutThreshold"),
        "lockout_duration_minutes": interval_to_minutes(i("lockoutDuration")),
        "lockout_window_minutes": interval_to_minutes(i("lockOutObservationWindow")),
    }


def collect(t: LdapTarget) -> dict[str, object]:
    from ldap3 import BASE, SUBTREE

    conn = connect(t)
    users = []
    entries = conn.extend.standard.paged_search(
        t.base_dn, "(&(objectCategory=person)(objectClass=user))", SUBTREE,
        attributes=USER_ATTRS, paged_size=500, generator=True)
    for e in entries:
        if e.get("type") == "searchResEntry":
            users.append(normalize_user(e["dn"], e["attributes"]))
    users.sort(key=lambda u: u["sam"].lower())

    groups = {}
    for g in PRIVILEGED_AD_GROUPS + APP_GROUPS:
        conn.search(t.base_dn, f"(&(objectClass=group)(cn={g}))", SUBTREE, attributes=["distinguishedName"])
        if not conn.entries:
            continue
        gdn = conn.entries[0].entry_dn
        conn.search(t.base_dn, f"(&(objectClass=user)(memberOf:{IN_CHAIN}:={gdn}))", SUBTREE,
                    attributes=["sAMAccountName"])
        groups[g] = sorted(str(first(e.entry_attributes_as_dict, "sAMAccountName")) for e in conn.entries)

    conn.search(t.base_dn, "(objectClass=domain)", BASE, attributes=POLICY_ATTRS)
    d = conn.entries[0].entry_attributes_as_dict
    policy = normalize_policy(d)
    psos = []
    conn.search(f"CN=Password Settings Container,CN=System,{t.base_dn}", "(objectClass=msDS-PasswordSettings)",
                SUBTREE, attributes=PSO_ATTRS)
    for p in conn.entries:
        a = p.entry_attributes_as_dict
        psos.append({"name": first(a, "cn"),
                     "precedence": int(first(a, "msDS-PasswordSettingsPrecedence") or 0),
                     "min_length": int(first(a, "msDS-MinimumPasswordLength") or 0),
                     "complexity": first(a, "msDS-PasswordComplexityEnabled"),
                     "applies_to": sorted(cn_of(str(x)) for x in a.get("msDS-PSOAppliesTo", []))})
    policy["fine_grained_policies"] = psos
    policy["fine_grained_policies_note"] = (
        "PSO objects readable by the audit account" if psos else
        "No PSOs returned: none exist OR the read-only audit account lacks rights to read them "
        "(default AD ACLs restrict PSOs to Domain Admins). Request a DA-run export if relevant.")
    conn.unbind()
    return {"ad_users.json": users, "ad_privileged_groups.json": groups, "ad_domain_policy.json": policy}
