import hashlib
import json
import shutil
import subprocess

import pytest

from itgc.collect.changes import collect_tags
from itgc.collect.manifest import verify_manifest, write_manifest
from itgc.lab_repo import build_repo
from itgc.scenario import generate

from .conftest import BASELINE


def test_manifest_detects_tampering(tmp_path):
    (tmp_path / "system").mkdir()
    f = tmp_path / "system" / "a.json"
    f.write_text("[1, 2]", encoding="utf-8")
    write_manifest(tmp_path, {})
    assert verify_manifest(tmp_path) == []
    f.write_text("[1, 3]", encoding="utf-8")
    assert verify_manifest(tmp_path) == ["hash mismatch: system/a.json"]


def _digest(root):
    h = hashlib.sha256()
    files = sorted((root / "audit" / "pbc").glob("*.csv")) + [root / "lab" / "seed" / "answer_key.json",
                                                            root / "lab" / ".build" / "ad_spec.json"]
    for p in files:
        h.update(p.read_bytes())
    return h.hexdigest()


def test_scenario_is_deterministic_and_matches_committed_pbc(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    counts = generate(a)
    generate(b)
    assert _digest(a) == _digest(b)
    assert counts["answer_key"] == 39 and counts["hr_roster.csv"] == 81
    for f in (a / "audit" / "pbc").glob("*.csv"):          # committed PBC == regenerated PBC
        assert f.read_bytes() == (BASELINE / "pbc" / f.name).read_bytes(), f.name


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_change_repo_build_and_collector(tmp_path):
    generate(tmp_path)
    repo, _ = build_repo(tmp_path / "lab" / ".build")
    tags = collect_tags(repo)
    assert len(tags) == 32
    committed = json.loads((BASELINE / "system" / "release_tags.json").read_text(encoding="utf-8"))
    assert [t["commit"] for t in tags] == [t["commit"] for t in committed]      # byte-identical history
    assert sum(len(t["migrations"]) for t in tags) == 11       # V001-V011; V012 never shipped (CM-04)
    status = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True)
    assert status.stdout == ""
