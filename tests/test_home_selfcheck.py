"""Homelab self-check against FICTIONAL fixtures (example.test names, no real network data)."""
import os
from datetime import UTC, datetime, timedelta

from itgc.home.selfcheck import (
    check_backups,
    check_edge,
    check_image_age,
    check_inline_secrets,
    check_lan_exposure,
    check_monitoring,
)

INGRESS = [
    {"hostname": "wiki.example.test", "service": "http://127.0.0.1:9000"},
    {"hostname": "photos.example.test", "service": "http://127.0.0.1:2283"},
    {"hostname": "llm.example.test", "service": "http://127.0.0.1:11434"},
    {"service": "http_status:404"},
]


def test_edge_exposure_classification():
    f = {x.item: x.status for x in check_edge(INGRESS, {"127.0.0.1:9000"}, {"photos.example.test"})}
    assert f == {"wiki.example.test": "pass", "photos.example.test": "review", "llm.example.test": "exception"}


def test_lan_exposure():
    rows = [{"Names": "a", "Ports": "0.0.0.0:8080->80/tcp, :::8080->80/tcp"},
            {"Names": "b", "Ports": "127.0.0.1:5432->5432/tcp"}, {"Names": "c", "Ports": ""}]
    f = {x.item: x.status for x in check_lan_exposure(rows)}
    assert f == {"a": "review", "b": "pass"}


def test_monitoring_matches_hostname_or_origin_port():
    f = {x.item: x.status for x in check_monitoring(INGRESS, ["http://host.internal:9000", "https://photos.example.test/"])}
    assert f == {"wiki.example.test": "pass", "photos.example.test": "pass", "llm.example.test": "exception"}


def test_backup_freshness(tmp_path):
    old, new = tmp_path / "2026-01-01", tmp_path / "2026-01-02"
    old.mkdir()
    new.mkdir()
    now = datetime.now(UTC)
    stamp = (now - timedelta(hours=30)).timestamp()
    os.utime(old, (stamp, stamp))
    os.utime(new, (stamp, stamp))
    (tmp_path / "backup.log").write_text("dump ok\nERROR: disk full\n", encoding="utf-8")
    f = check_backups(tmp_path, 26, now)
    assert [x.status for x in f] == ["exception", "exception"]


def test_image_age_and_secrets(tmp_path):
    now = datetime(2026, 10, 1, tzinfo=UTC)
    imgs = [{"Repository": "app", "Tag": "1", "CreatedAt": "2025-01-01 00:00:00 +0000 UTC"},
            {"Repository": "db", "Tag": "2", "CreatedAt": "2026-09-01 00:00:00 +0000 UTC"}]
    assert [x.item for x in check_image_age(imgs, 180, now)] == ["app:1"]
    d = tmp_path / "svc"
    d.mkdir()
    (d / "docker-compose.yml").write_text("environment:\n  - DB_PASSWORD=hunter2\n  - API_TOKEN=${TOKEN}\n", encoding="utf-8")
    f = check_inline_secrets([d / "docker-compose.yml"])
    assert f[0].status == "exception" and "1 inline" in f[0].detail and "hunter2" not in f[0].detail
