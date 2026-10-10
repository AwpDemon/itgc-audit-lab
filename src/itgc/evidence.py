"""Load an evidence bundle (system evidence + PBC documents + criteria) into one object."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def _json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Evidence:
    root: Path
    users: list[dict] = field(default_factory=list)
    priv_groups: dict[str, list[str]] = field(default_factory=dict)
    policy: dict = field(default_factory=dict)
    erp_users: list[dict] = field(default_factory=list)
    db_roles: list[dict] = field(default_factory=list)
    migrations: list[dict] = field(default_factory=list)
    tags: list[dict] = field(default_factory=list)
    deploy_log: list[dict] = field(default_factory=list)
    restore: dict | None = None
    manifest: dict = field(default_factory=dict)
    pbc: dict[str, list[dict]] = field(default_factory=dict)
    standard: dict = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path) -> Evidence:
        s, p = root / "system", root / "pbc"
        ev = cls(root=root)
        ev.users = _json(s / "ad_users.json", [])
        ev.priv_groups = _json(s / "ad_privileged_groups.json", {})
        ev.policy = _json(s / "ad_domain_policy.json", {})
        ev.erp_users = _json(s / "erp_users.json", [])
        ev.db_roles = _json(s / "db_roles.json", [])
        ev.migrations = _json(s / "schema_migrations.json", [])
        ev.tags = _json(s / "release_tags.json", [])
        ev.deploy_log = _json(s / "deploy_log.json", [])
        ev.restore = _json(s / "restore_test.json", None)
        ev.manifest = _json(root / "manifest.json", {})
        for f in sorted(p.glob("*.csv")):
            ev.pbc[f.stem] = _csv(f)
        std = p / "it_security_standard.yaml"
        ev.standard = yaml.safe_load(std.read_text(encoding="utf-8")) if std.exists() else {}
        return ev

    # convenience lookups -------------------------------------------------
    def user(self, sam: str) -> dict | None:
        s = sam.lower()
        return next((u for u in self.users if (u.get("sam") or "").lower() == s), None)

    def erp_user(self, name: str) -> dict | None:
        return next((u for u in self.erp_users if u["username"].lower() == name.lower()), None)

    @property
    def hr(self) -> list[dict]:
        return self.pbc.get("hr_roster", [])

    def hr_by_sam(self) -> dict[str, dict]:
        return {r["network_id"].lower(): r for r in self.hr}

    def hr_by_emp(self) -> dict[str, dict]:
        return {r["employee_id"]: r for r in self.hr}
