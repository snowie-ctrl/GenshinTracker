from app.config import Paths
from app.devseed import seed
from helpers import make_client


def test_devseed_creates_expected_statuses(tmp_path):
    seed(tmp_path)
    seed(tmp_path)  # re-seeding starts fresh
    paths = Paths(tmp_path)
    with make_client(paths) as client:
        chars = {c["slug"]: c for c in client.get("/api/characters").json()}
        dash = client.get("/api/dashboard").json()
    statuses = {slug: (c["status"], c["prefarming"]) for slug, c in chars.items()}
    assert statuses == {
        "bennett": ("building", False), "furina": ("building", False),
        "xiangling": ("obtained", False), "nahida": ("obtained", False),
        "kazuha": ("wanted", False), "neuvillette": ("wanted", True),
        "raiden-shogun": ("unobtained", False), "xingqiu": ("unobtained", False),
    }
    assert dash["notes"]["resin"] == 120
