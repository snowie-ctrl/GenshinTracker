from app.db.models import HoyolabSnapshot
from app.timeutil import utcnow
from helpers import make_client
from test_api_planner import sf_for
from test_profile_view import DATA


def test_profile_endpoint(paths):
    sf = sf_for(paths)
    with make_client(paths) as client:
        empty = client.get("/api/profile").json()
        assert empty["profile"] is None and empty["fetched_at"] is None
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="profile", data=DATA, fetched_at=utcnow()))
    with make_client(paths) as client:
        body = client.get("/api/profile").json()
        dash = client.get("/api/dashboard").json()
    assert body["profile"]["ar"] == 60 and set(body["challenges"]) == {"abyss", "theater", "stygian"}
    assert dash["profile_summary"]["ar"] == 60 and dash["profile_summary"]["fetched_at"].endswith("Z")
