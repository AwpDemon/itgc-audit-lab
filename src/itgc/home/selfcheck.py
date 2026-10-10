"""Read-only ITGC-style self-check for a self-hosted homelab.

Applies the same control objectives as the main audit (logical access, change, operations) to
a typical homelab built from Docker containers behind an outbound-only tunnel with an SSO
proxy. Every check only READS configuration or state; nothing is changed.

Checks
  H1 edge exposure   every internet-published hostname routes through the SSO proxy (or is
                     on an explicit allow-list of apps with their own authentication)
  H2 LAN exposure    container ports published on all interfaces (0.0.0.0 / ::) vs. loopback
  H3 backups         newest backup is younger than the allowed age and the last log line is OK
  H4 monitoring      every internet-published hostname has an uptime monitor
  H5 patch currency  container images older than N days (rebuild / update cadence)
  H6 secrets hygiene compose files with inline secret-looking values (values never printed)

The output is a findings report. By design, real results for the author's own network are
written only to a git-ignored folder and never committed (no hostnames, IPs or weaknesses
are published); the repository's tests run against fictional fixtures.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

SECRET_KEY = re.compile(r"^\s*-?\s*([A-Z0-9_]*(PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|APIKEY|PRIVATE_KEY)[A-Z0-9_]*)\s*[:=]\s*(.+)$",
                        re.IGNORECASE)


@dataclass
class Finding:
    check: str
    item: str
    status: str            # pass | exception | review
    detail: str
    objective: str = ""


@dataclass
class Report:
    generated_at: str
    findings: list[Finding] = field(default_factory=list)

    def summary(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for f in self.findings:
            out.setdefault(f.check, {}).setdefault(f.status, 0)
            out[f.check][f.status] += 1
        return out


OBJECTIVES = {
    "H1": "Internet-facing applications require centrally managed authentication (SSO) - logical access",
    "H2": "Services are not exposed on more interfaces than needed - logical access / network",
    "H3": "Backups run on schedule and their success is evidenced - operations",
    "H4": "Every internet-facing service is monitored for availability - operations",
    "H5": "Software is kept current through a regular update cadence - change management",
    "H6": "Secrets are not stored in plain text in configuration under change control - change/access",
}


# ----------------------------------------------------------------------- pure checks (unit-tested)
def check_edge(ingress: list[dict], sso_origins: set[str], own_auth_allow: set[str]) -> list[Finding]:
    out = []
    for rule in ingress:
        host = rule.get("hostname")
        if not host:
            continue                               # catch-all rule
        origin = urlparse(str(rule.get("service", "")))
        target = f"{origin.hostname}:{origin.port}" if origin.port else str(origin.hostname)
        if target in sso_origins:
            out.append(Finding("H1", host, "pass", "routed through SSO proxy"))
        elif host in own_auth_allow:
            out.append(Finding("H1", host, "review", "bypasses SSO; on allow-list (app has own authentication)"))
        else:
            out.append(Finding("H1", host, "exception", "published directly, not through the SSO proxy"))
    return out


def check_lan_exposure(containers: list[dict]) -> list[Finding]:
    out = []
    for c in containers:
        ports = c.get("Ports", "") or ""
        wide = [p.strip() for p in ports.split(",") if p.strip().startswith(("0.0.0.0:", ":::", "[::]:"))]
        if wide:
            out.append(Finding("H2", c.get("Names", "?"), "review", f"{len(wide)} port mapping(s) bound to all interfaces"))
        elif ports:
            out.append(Finding("H2", c.get("Names", "?"), "pass", "published ports bound to loopback only"))
    return out


def check_backups(backup_root: Path, max_age_hours: float, now: datetime, log_ok_pattern: str = "OK|success|done") -> list[Finding]:
    if not backup_root.exists():
        return [Finding("H3", backup_root.name, "exception", "backup location not found")]
    entries = [p for p in backup_root.iterdir() if p.is_dir()]
    if not entries:
        return [Finding("H3", backup_root.name, "exception", "no backup sets present")]
    newest = max(entries, key=lambda p: p.stat().st_mtime)
    age_h = (now.timestamp() - newest.stat().st_mtime) / 3600
    out = [Finding("H3", "newest backup set", "pass" if age_h <= max_age_hours else "exception",
                   f"age {age_h:.1f} h (limit {max_age_hours} h); {len(entries)} sets retained")]
    log = backup_root / "backup.log"
    if log.exists():
        tail = [ln for ln in log.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()][-5:]
        bad = [ln for ln in tail if re.search(r"error|fail", ln, re.IGNORECASE)]
        ok = any(re.search(log_ok_pattern, ln, re.IGNORECASE) for ln in tail)
        out.append(Finding("H3", "backup log tail", "exception" if bad else ("pass" if ok else "review"),
                           f"{len(bad)} error line(s) in last {len(tail)} lines"))
    return out


def check_monitoring(ingress: list[dict], monitored_urls: list[str]) -> list[Finding]:
    """A published hostname counts as monitored if a monitor targets the hostname itself or the
    origin port it routes to (many homelabs monitor origins, which skips the tunnel path - noted)."""
    parsed = [urlparse(u) for u in monitored_urls if u]
    hosts = {p.hostname for p in parsed}
    ports = {p.port for p in parsed if p.port}
    out = []
    for rule in ingress:
        h = rule.get("hostname")
        if not h:
            continue
        port = urlparse(str(rule.get("service", ""))).port
        if h in hosts:
            out.append(Finding("H4", h, "pass", "external (through-the-edge) monitor present"))
        elif port in ports:
            out.append(Finding("H4", h, "pass", "origin monitored (edge path itself not monitored)"))
        else:
            out.append(Finding("H4", h, "exception", "no uptime monitor for this hostname or its origin"))
    return out


def check_image_age(images: list[dict], max_age_days: int, now: datetime) -> list[Finding]:
    out = []
    for im in images:
        created = im.get("CreatedAt", "")
        try:
            dt = datetime.strptime(created[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            continue
        age = (now - dt).days
        name = f"{im.get('Repository')}:{im.get('Tag')}"
        if age > max_age_days:
            out.append(Finding("H5", name, "review", f"image built {age} days ago (> {max_age_days})"))
    if not out:
        out.append(Finding("H5", "all images", "pass", f"no image older than {max_age_days} days"))
    return out


def check_inline_secrets(compose_files: list[Path]) -> list[Finding]:
    out = []
    for f in compose_files:
        hits = 0
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = SECRET_KEY.match(line)
            if m and not m.group(3).strip().startswith(("${", "$", "/run/secrets", "!")) and m.group(3).strip() not in ('""', "''"):
                hits += 1
        out.append(Finding("H6", f.parent.name + "/" + f.name, "exception" if hits else "pass",
                           f"{hits} inline secret-looking value(s) (values not printed)" if hits else "no inline secrets"))
    return out


# ----------------------------------------------------------------------- collectors (read-only I/O)
def _docker_json(cmd: list[str]) -> list[dict]:
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return [json.loads(ln) for ln in out.splitlines() if ln.strip()]


def kuma_monitor_urls(db: Path) -> list[str]:
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute("select url from monitor where active = 1 and url is not null")]
    finally:
        con.close()


def run(args) -> Report:
    now = datetime.now(UTC)
    rep = Report(generated_at=now.isoformat(timespec="seconds"))
    ingress = []
    if args.tunnel_config:
        ingress = yaml.safe_load(Path(args.tunnel_config).read_text(encoding="utf-8")).get("ingress", [])
        rep.findings += check_edge(ingress, set(args.sso_origin), set(args.own_auth or []))
    if args.docker_cmd:
        base = args.docker_cmd.split()
        rep.findings += check_lan_exposure(_docker_json(base + ["ps", "--format", "{{json .}}"]))
        rep.findings += check_image_age(_docker_json(base + ["image", "ls", "--format", "{{json .}}"]), args.max_image_age_days, now)
    if args.backup_dir:
        rep.findings += check_backups(Path(args.backup_dir), args.max_backup_age_hours, now)
    if args.kuma_db and ingress:
        rep.findings += check_monitoring(ingress, kuma_monitor_urls(Path(args.kuma_db)))
    if args.compose_root:
        rep.findings += check_inline_secrets(sorted(Path(args.compose_root).glob("*/docker-compose.y*ml")))
    for f in rep.findings:
        f.objective = OBJECTIVES[f.check]
    return rep


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tunnel-config")
    ap.add_argument("--sso-origin", action="append", default=[], help="host:port of the SSO proxy origin")
    ap.add_argument("--own-auth", action="append", help="hostname allowed to bypass SSO (has its own auth)")
    ap.add_argument("--docker-cmd", help="e.g. 'docker' or 'wsl -d Ubuntu docker'")
    ap.add_argument("--backup-dir")
    ap.add_argument("--max-backup-age-hours", type=float, default=26)
    ap.add_argument("--kuma-db", help="Uptime Kuma sqlite DB (opened read-only)")
    ap.add_argument("--compose-root")
    ap.add_argument("--max-image-age-days", type=int, default=180)
    ap.add_argument("--out", default="home/private/selfcheck.json", help="git-ignored by default")
    args = ap.parse_args(argv)
    rep = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated_at": rep.generated_at, "summary": rep.summary(),
                               "findings": [asdict(f) for f in rep.findings]}, indent=1), encoding="utf-8")
    print(json.dumps(rep.summary(), indent=1))
    print(f"report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
