"""Build the ERP order-portal git repository and its CI/CD deployment log from releases.json.

The repository is the *system* whose change history the auditor tests: every production
release is an annotated tag created by whoever deployed it, and the pipeline appends a row to
``cicd/deploy_log.csv``. Commits are back-dated with GIT_AUTHOR_DATE / GIT_COMMITTER_DATE so
the history spans the audit period; identities are passed per-command via environment
variables (no git config is changed). Same input -> byte-identical repo (same SHAs).
"""
from __future__ import annotations

import csv
import json
import os
import random
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

FILES = ["app/orders.py", "app/pricing.py", "app/invoices.py", "app/reports.py", "app/auth.py"]


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    full_env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, **(env or {})}
    out = subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false",
                          "-c", "init.defaultBranch=main", "-c", "core.autocrlf=false", *args],
                         cwd=repo, env=full_env, check=True, capture_output=True, text=True)
    return out.stdout.strip()


def _ident(person: dict, when: datetime, role: str) -> dict:
    stamp = when.strftime("%Y-%m-%dT%H:%M:%S") + " +0000"
    return {f"GIT_{role}_NAME": person["name"], f"GIT_{role}_EMAIL": person["email"], f"GIT_{role}_DATE": stamp}


def build_repo(build_dir: Path) -> tuple[Path, Path]:
    releases = json.loads((build_dir / "releases.json").read_text(encoding="utf-8"))
    repo = build_dir / "order-portal"
    if repo.exists():
        shutil.rmtree(repo, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))
    repo.mkdir(parents=True)
    rng = random.Random(7)
    _git(repo, "init", "-q")
    bootstrap = {"name": "Initial Import", "email": "import@kestrel-valve.example"}
    for f in FILES:
        (repo / f).parent.mkdir(parents=True, exist_ok=True)
        (repo / f).write_text(f'"""{f} - Kestrel order portal (lab stub)."""\n', encoding="utf-8", newline="\n")
    (repo / "db" / "migrations").mkdir(parents=True)
    (repo / "db" / "migrations" / ".keep").write_text("", encoding="utf-8", newline="\n")
    t0 = datetime(2025, 9, 1, 9, 0)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Baseline import of order portal", env=_ident(bootstrap, t0, "AUTHOR") | _ident(bootstrap, t0, "COMMITTER"))

    deploy_rows = []
    for n, rel in enumerate(releases, start=1):
        deployed = datetime.fromisoformat(rel["deployed_at"])
        author = rel["author"]
        for k in range(rel["n_commits"]):
            when = deployed - timedelta(days=rng.randint(1, 5), hours=rng.randint(1, 9), minutes=k)
            f = repo / rng.choice(FILES)
            with f.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(f"# change {n}.{k}: {rel['tag']}\n")
            msg = f"{rel['change_id'] or 'no-ticket'}: update {f.name} ({k + 1}/{rel['n_commits']})"
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", msg, env=_ident(author, when, "AUTHOR") | _ident(author, when, "COMMITTER"))
        for v in rel["migrations"]:
            mig = repo / "db" / "migrations" / f"{v}__release_{n}.sql"
            mig.write_text(f"-- {v} shipped in {rel['tag']}\nALTER TABLE app.invoices ADD COLUMN IF NOT EXISTS c{n} text;\n",
                           encoding="utf-8", newline="\n")
            when = deployed - timedelta(days=1)
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", f"{rel['change_id'] or 'no-ticket'}: migration {v}",
                 env=_ident(author, when, "AUTHOR") | _ident(author, when, "COMMITTER"))
        tag_msg = f"Production release {rel['tag']}\n\nChange: {rel['change_id'] or 'none'}\n"
        _git(repo, "tag", "-a", rel["tag"], "-m", tag_msg, env=_ident(rel["deployer"], deployed, "COMMITTER"))
        sha = _git(repo, "rev-list", "-n", "1", rel["tag"])
        deploy_rows.append({"pipeline_run": f"run-{4100 + n}", "environment": "production", "tag": rel["tag"],
                            "commit": sha, "deployed_at": rel["deployed_at"], "deployed_by": rel["deployer"]["sam"],
                            "result": "success"})
    log = build_dir / "cicd" / "deploy_log.csv"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(deploy_rows[0]))
        w.writeheader()
        w.writerows(deploy_rows)
    return repo, log
