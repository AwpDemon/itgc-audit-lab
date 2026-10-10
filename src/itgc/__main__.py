"""Command line entry point: python -m itgc <command>.

  scenario   generate the fictional company: lab seeds + PBC documents + answer key
  build-repo build the order-portal git repo + CI/CD deploy log from the scenario
  collect    pull evidence from the running lab into audit/evidence/<label>/
  audit      run the control tests on an evidence bundle -> results, workpapers, letter, figures
  compare    baseline vs post-remediation re-test (table + figure)
  verify     check an evidence bundle against its SHA-256 manifest
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="itgc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scenario")
    sub.add_parser("build-repo")

    c = sub.add_parser("collect")
    c.add_argument("--label", default="fy26-baseline")
    c.add_argument("--ldap-host", default=_env("ITGC_LDAP_HOST", "127.0.0.1"))
    c.add_argument("--ldap-port", type=int, default=int(_env("ITGC_LDAP_PORT", "1636")))
    c.add_argument("--ldap-user", default=_env("ITGC_LDAP_USER", "svc_audit_ro@kestrel.lab.test"))
    c.add_argument("--ldap-password", default=_env("ITGC_LDAP_PASSWORD", "Lab-Audit-ReadOnly-2026!"))
    c.add_argument("--base-dn", default="DC=kestrel,DC=lab,DC=test")
    c.add_argument("--ca-file", default=_env("ITGC_LDAP_CA"), help="CA PEM to validate the DC's LDAPS certificate")
    c.add_argument("--tls-name", default="DC1.kestrel.lab.test")
    c.add_argument("--pg-dsn", default=_env("ITGC_PG_DSN", "host=127.0.0.1 port=15432 dbname=erp user=audit_ro "
                                                        "password=lab-only-audit-ro"))
    c.add_argument("--restore-json", help="output of lab/scripts/restore_test.sh (auditor re-performance)")
    c.add_argument("--skip-ldap", action="store_true")
    c.add_argument("--skip-db", action="store_true")

    a = sub.add_parser("audit")
    a.add_argument("--evidence", default="audit/evidence/fy26-baseline")
    a.add_argument("--out", default=None, help="output dir (default: audit/results/<evidence label>)")
    a.add_argument("--no-figures", action="store_true")

    cp = sub.add_parser("compare", help="baseline vs re-test comparison")
    cp.add_argument("--before", default="audit/results/fy26-baseline")
    cp.add_argument("--after", default="audit/results/fy26-remediation")

    v = sub.add_parser("verify")
    v.add_argument("evidence")

    args = ap.parse_args(argv)
    if args.cmd == "scenario":
        from .scenario import generate
        counts = generate(ROOT)
        for k, n in counts.items():
            print(f"{k:38s} {n:5d}")
        return 0
    if args.cmd == "build-repo":
        from .lab_repo import build_repo
        repo, log = build_repo(ROOT / "lab" / ".build")
        print(f"repo: {repo}\ndeploy log: {log}")
        return 0
    if args.cmd == "collect":
        from .collect.ad import LdapTarget
        from .collect.run import run
        ldap = None if args.skip_ldap else LdapTarget(args.ldap_host, args.ldap_port, args.ldap_user,
                                                      args.ldap_password, args.base_dn, args.ca_file, args.tls_name)
        build = ROOT / "lab" / ".build"
        out = run(ROOT / "audit" / "evidence" / args.label, ldap=ldap, dsn=None if args.skip_db else args.pg_dsn,
                  repo=build / "order-portal", deploy_log=build / "cicd" / "deploy_log.csv",
                  restore_json=Path(args.restore_json) if args.restore_json else None,
                  pbc_dir=ROOT / "audit" / "pbc", label=args.label)
        print(f"evidence bundle: {out}")
        return 0
    if args.cmd == "audit":
        from .engine import run_audit
        ev = (ROOT / args.evidence) if not Path(args.evidence).is_absolute() else Path(args.evidence)
        out = Path(args.out) if args.out else ROOT / "audit" / "results" / ev.name
        summary = run_audit(ev, out, figures=not args.no_figures)
        print(summary)
        return 0
    if args.cmd == "compare":
        from .compare import compare
        print(compare(ROOT / args.before, ROOT / args.after, ROOT / "audit" / "results" / "remediation_comparison.md",
                      ROOT / "docs" / "figures"))
        return 0
    if args.cmd == "verify":
        from .collect.manifest import verify_manifest
        problems = verify_manifest(Path(args.evidence))
        print("OK: all evidence hashes match" if not problems else "\n".join(problems))
        return 1 if problems else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
