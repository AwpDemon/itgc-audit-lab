from datetime import UTC, date, datetime

from itgc.ad import cn_of, decode_uac, interval_to_days, interval_to_minutes, is_enabled, ou_path
from itgc.collect.ad import gen_time, normalize_policy, normalize_user
from itgc.dates import add_business_days, business_days_between, from_filetime, to_filetime


def test_filetime_round_trip():
    dt = datetime(2026, 2, 25, 21, 14, tzinfo=UTC)
    assert from_filetime(to_filetime(dt)) == dt
    assert from_filetime(0) is None and from_filetime("9223372036854775807") is None


def test_business_days_skip_weekends():
    fri = date(2026, 2, 20)
    assert add_business_days(fri, 1) == date(2026, 2, 23)          # Monday
    assert business_days_between(fri, date(2026, 2, 23)) == 1
    assert business_days_between(date(2026, 2, 19), date(2026, 3, 4)) == 9
    assert business_days_between(fri, fri) == 0


def test_decode_uac():
    assert decode_uac(512) == ["NORMAL_ACCOUNT"]
    assert decode_uac(66050) == ["ACCOUNTDISABLE", "NORMAL_ACCOUNT", "DONT_EXPIRE_PASSWORD"]
    assert "PASSWD_NOTREQD" in decode_uac(544)
    assert is_enabled(512) and not is_enabled(514)


def test_dn_helpers_and_intervals():
    dn = "CN=klee,OU=Users,OU=Kestrel,DC=kestrel,DC=lab,DC=test"
    assert cn_of(dn) == "klee" and ou_path(dn) == "OU=Users,OU=Kestrel"
    assert interval_to_days(-77760000000000) == 90.0
    assert interval_to_minutes(-18000000000) == 30.0
    assert gen_time("20240611100000.0Z") == "2024-06-11T10:00:00+00:00"


def test_normalize_user_from_raw_ldap_attributes():
    raw = {"sAMAccountName": ["klee"], "userAccountControl": ["66048"], "employeeID": ["E1070"],
           "whenCreated": ["20240611100000.0Z"], "lastLogonTimestamp": [str(to_filetime(datetime(2026, 2, 25, 21, 14)))],
           "memberOf": ["CN=GG-Sales,OU=Groups,DC=x", "CN=APP-ERP-Users,OU=Groups,DC=x"],
           "manager": ["CN=prossi,OU=Users,DC=x"]}
    u = normalize_user("CN=klee,OU=Users,OU=Kestrel,DC=x", raw)
    assert u["sam"] == "klee" and u["enabled"] is True
    assert u["uac_flags"] == ["NORMAL_ACCOUNT", "DONT_EXPIRE_PASSWORD"]
    assert u["member_of"] == ["APP-ERP-Users", "GG-Sales"]
    assert u["last_logon_timestamp"].startswith("2026-02-25T21:14")
    assert u["manager"] == "prossi"


def test_normalize_policy():
    p = normalize_policy({"minPwdLength": ["8"], "pwdProperties": ["1"], "pwdHistoryLength": ["24"],
                          "maxPwdAge": ["-77760000000000"], "minPwdAge": ["-864000000000"],
                          "lockoutThreshold": ["0"], "lockoutDuration": ["-18000000000"],
                          "lockOutObservationWindow": ["-18000000000"]})
    assert p["min_pwd_length"] == 8 and p["complexity_enabled"] and p["lockout_threshold"] == 0
    assert p["max_pwd_age_days"] == 90.0 and p["min_pwd_age_days"] == 1.0
