"""Active Directory helpers: userAccountControl decoding, DN parsing, privileged-group catalogue."""
from __future__ import annotations

# https://learn.microsoft.com/troubleshoot/windows-server/active-directory/useraccountcontrol-manipulate-account-properties
UAC_FLAGS = {
    0x0002: "ACCOUNTDISABLE",
    0x0010: "LOCKOUT",
    0x0020: "PASSWD_NOTREQD",
    0x0040: "PASSWD_CANT_CHANGE",
    0x0080: "ENCRYPTED_TEXT_PWD_ALLOWED",
    0x0200: "NORMAL_ACCOUNT",
    0x0800: "INTERDOMAIN_TRUST_ACCOUNT",
    0x1000: "WORKSTATION_TRUST_ACCOUNT",
    0x2000: "SERVER_TRUST_ACCOUNT",
    0x10000: "DONT_EXPIRE_PASSWORD",
    0x40000: "SMARTCARD_REQUIRED",
    0x80000: "TRUSTED_FOR_DELEGATION",
    0x100000: "NOT_DELEGATED",
    0x200000: "USE_DES_KEY_ONLY",
    0x400000: "DONT_REQ_PREAUTH",
    0x800000: "PASSWORD_EXPIRED",
    0x1000000: "TRUSTED_TO_AUTH_FOR_DELEGATION",
}

# Groups whose members can take over the domain or its data (Microsoft "protected groups" + tier 0).
PRIVILEGED_AD_GROUPS = [
    "Domain Admins", "Enterprise Admins", "Schema Admins", "Administrators",
    "Account Operators", "Backup Operators", "Server Operators", "Print Operators",
    "Group Policy Creator Owners", "DnsAdmins",
]

# pwdProperties bit flags on the domain object
DOMAIN_PASSWORD_COMPLEX = 0x1


def decode_uac(value: int | str) -> list[str]:
    v = int(value)
    return [name for bit, name in sorted(UAC_FLAGS.items()) if v & bit]


def is_enabled(uac: int | str) -> bool:
    return not int(uac) & 0x0002


def cn_of(dn: str) -> str:
    """First RDN value of a DN: 'CN=Domain Admins,CN=Users,DC=x' -> 'Domain Admins'."""
    first = dn.split(",", 1)[0]
    return first.split("=", 1)[1] if "=" in first else first


def ou_path(dn: str) -> str:
    """OU part of a DN, e.g. 'OU=Users,OU=Kestrel' ('' when the object is in a container)."""
    parts = [p for p in dn.split(",")[1:] if p.upper().startswith("OU=")]
    return ",".join(parts)


def interval_to_days(value: int | str | None) -> float | None:
    """AD stores maxPwdAge etc. as negative 100-ns intervals. -864000000000 == 1 day."""
    if value in (None, ""):
        return None
    v = int(value)
    if v == -0x8000000000000000 or v == 0:
        return 0.0
    return abs(v) / 864_000_000_000


def interval_to_minutes(value: int | str | None) -> float | None:
    if value in (None, ""):
        return None
    return abs(int(value)) / 600_000_000
