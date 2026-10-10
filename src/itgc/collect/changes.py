"""Collect the production change population from the application's git repo and CI/CD log.

Two independent system sources are captured so the auditor can test completeness of the
population (every deployment has a tag and vice versa) before sampling from it.
"""
from __future__ import annotations

import csv
import subprocess
from pathlib import Path

SEP = "\x1f"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def collect_tags(repo: Path) -> list[dict]:
    fmt = SEP.join(["%(refname:short)", "%(objectname)", "%(*objectname)", "%(taggername)",
                    "%(taggeremail)", "%(taggerdate:iso-strict)", "%(contents:body)"])
    raw = _git(repo, "for-each-ref", "--sort=taggerdate", f"--format={fmt}{SEP}{SEP}", "refs/tags")
    tags = []
    prev_commit = _git(repo, "rev-list", "--max-parents=0", "HEAD").split()[0]   # baseline import
    prev_migs: set[str] = set()
    for rec in raw.split(SEP + SEP):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        name, tag_obj, commit, tagger, email, when, body = (rec.split(SEP) + [""] * 7)[:7]
        rng = f"{prev_commit}..{commit}"
        log = _git(repo, "log", "--no-merges", f"--format=%H{SEP}%an{SEP}%ae{SEP}%aI{SEP}%s", rng)
        commits = []
        for line in log.splitlines():
            h, an, ae, ad, subj = line.split(SEP)
            commits.append({"sha": h, "author": an, "author_email": ae, "authored_at": ad, "subject": subj})
        migs = {Path(p).name for p in _git(repo, "ls-tree", "-r", "--name-only", commit, "db/migrations").splitlines()
                if p.endswith(".sql")}
        change_ref = ""
        for line in body.splitlines():
            if line.lower().startswith("change:"):
                change_ref = line.split(":", 1)[1].strip()
        tags.append({"tag": name.strip(), "tag_object": tag_obj, "commit": commit, "tagger": tagger,
                     "tagger_email": email.strip("<>"), "tagged_at": when, "change_ref_in_tag": change_ref,
                     "commits": commits, "migrations": sorted(migs - prev_migs)})
        prev_commit, prev_migs = commit, migs
    return tags


def collect(repo: Path, deploy_log: Path) -> dict[str, object]:
    with deploy_log.open(newline="", encoding="utf-8") as fh:
        deployments = list(csv.DictReader(fh))
    head = _git(repo, "rev-parse", "HEAD").strip()
    return {"release_tags.json": collect_tags(repo), "deploy_log.json": deployments,
            "change_repo_info.json": {"head": head, "tag_count": int(_git(repo, "tag").count("\n"))}}
