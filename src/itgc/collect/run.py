"""Orchestrate one evidence-collection run into audit/evidence/<label>/."""
from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from . import ad as ad_collector
from . import changes as change_collector
from . import erp as erp_collector
from .manifest import write_manifest

PROVENANCE = {
    "ad_users.json": {"source": "Active Directory (Samba 4 AD DC)", "method": "LDAPS paged search "
                      "(&(objectCategory=person)(objectClass=user)) as read-only svc_audit_ro"},
    "ad_privileged_groups.json": {"source": "Active Directory", "method": "LDAP_MATCHING_RULE_IN_CHAIN "
                                  "recursive membership per privileged/app group"},
    "ad_domain_policy.json": {"source": "Active Directory", "method": "Base search on domain head + PSO container"},
    "erp_users.json": {"source": "ERP database (PostgreSQL)", "method": "SELECT app.users + app.user_roles as audit_ro"},
    "db_roles.json": {"source": "ERP database (PostgreSQL)", "method": "SELECT pg_roles / pg_auth_members as audit_ro"},
    "schema_migrations.json": {"source": "ERP database (PostgreSQL)", "method": "SELECT public.schema_migrations"},
    "erp_db_info.json": {"source": "ERP database (PostgreSQL)", "method": "current_user, version(), now()"},
    "release_tags.json": {"source": "order-portal git repository", "method": "git for-each-ref refs/tags + git log per release"},
    "deploy_log.json": {"source": "CI/CD pipeline deployment log", "method": "Export of production deployments"},
    "change_repo_info.json": {"source": "order-portal git repository", "method": "git rev-parse HEAD"},
    "restore_test.json": {"source": "Auditor re-performance", "method": "lab/scripts/restore_test.sh "
                          "(pg_dump -> pg_restore into scratch DB -> per-table count + md5 compare)"},
}


def _dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8", newline="\n")


def run(out_dir: Path, *, ldap: ad_collector.LdapTarget | None, dsn: str | None, repo: Path | None,
        deploy_log: Path | None, restore_json: Path | None, pbc_dir: Path, label: str) -> Path:
    system = out_dir / "system"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    system.mkdir(parents=True)
    collected: dict[str, object] = {}
    if ldap:
        collected |= ad_collector.collect(ldap)
    if dsn:
        collected |= erp_collector.collect(dsn)
    if repo and deploy_log:
        collected |= change_collector.collect(repo, deploy_log)
    for name, data in collected.items():
        _dump(system / name, data)
    if restore_json:
        _dump(system / "restore_test.json", json.loads(Path(restore_json).read_text(encoding="utf-8-sig")))
    pbc_out = out_dir / "pbc"
    shutil.copytree(pbc_dir, pbc_out)
    write_manifest(out_dir, PROVENANCE, extra={
        "label": label,
        "collected_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ldap_tls_validated": bool(ldap and ldap.ca_file),
        "audit_accounts": {"ldap": ldap.user if ldap else None, "postgres": "audit_ro" if dsn else None},
        "note": "system/ = pulled from lab systems by the collectors; pbc/ = management-provided documents "
                "(synthetic). Hashes let anyone verify the workpapers were built from this exact evidence."})
    return out_dir
