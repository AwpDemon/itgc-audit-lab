"""Evidence manifest: SHA-256 + record counts + provenance for every evidence file.

Auditors must be able to show evidence was not altered after collection and where each
population came from (IPE - information produced by the entity). The manifest records the
source system, the query/command, the account used, and a hash of every file.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def count_records(path: Path) -> int | None:
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        return len(data) if isinstance(data, list) else None
    if path.suffix == ".csv":
        lines = path.read_text(encoding="utf-8").splitlines()
        return max(len(lines) - 1, 0)
    return None


def write_manifest(bundle: Path, provenance: dict[str, dict], extra: dict | None = None) -> Path:
    files = []
    for p in sorted(bundle.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel = p.relative_to(bundle).as_posix()
            files.append({"file": rel, "sha256": sha256(p), "bytes": p.stat().st_size,
                          "records": count_records(p), **provenance.get(p.name, {})})
    manifest = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "files": files, **(extra or {})}
    out = bundle / "manifest.json"
    out.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return out


def verify_manifest(bundle: Path) -> list[str]:
    """Return a list of problems (empty == every file matches its recorded hash)."""
    m = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for f in m["files"]:
        p = bundle / f["file"]
        if not p.exists():
            problems.append(f"missing: {f['file']}")
        elif sha256(p) != f["sha256"]:
            problems.append(f"hash mismatch: {f['file']}")
    return problems
