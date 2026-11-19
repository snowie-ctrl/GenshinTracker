from fastapi.testclient import TestClient

from app.config import Paths, default_paths
from app.main import create_app
from app.timeutil import iso, utcnow


def test_health():
    client = TestClient(create_app())
    assert client.get("/api/health").json() == {"ok": True}


def test_paths_layout(tmp_path):
    p = Paths(tmp_path)
    p.ensure()
    assert p.db_file == tmp_path / "data" / "tracker.db"
    assert p.env_file == tmp_path / ".env"
    assert p.backups.is_dir() and p.img_cache.is_dir()


def test_default_paths_honours_gt_root(monkeypatch, tmp_path):
    monkeypatch.setenv("GT_ROOT", str(tmp_path))
    assert default_paths().root == tmp_path


def test_iso_is_utc_with_z():
    now = utcnow()
    assert now.tzinfo is None
    assert iso(now).endswith("Z")
    assert iso(None) is None
