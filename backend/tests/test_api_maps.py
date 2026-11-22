from helpers import make_client


def test_map_endpoint_and_default_setting(paths):
    with make_client(paths) as client:
        body = client.get("/api/map").json()
        assert [m["key"] for m in body["maps"]] == ["hoyolab", "appsample"] and body["default_map"] == "hoyolab"
        assert client.put("/api/settings", json={"default_map": "appsample"}).json()["default_map"] == "appsample"
        assert client.get("/api/map").json()["default_map"] == "appsample"
        assert client.put("/api/settings", json={"default_map": "google"}).status_code == 422
