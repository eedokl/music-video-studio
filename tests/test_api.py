"""HTTP API against a temporary projects folder."""

import pytest
from fastapi.testclient import TestClient

from conftest import make_line
from studio import store
from studio.main import app


@pytest.fixture
def client(projects):
    return TestClient(app)


def test_health(client):
    assert client.get("/api/health").status_code == 200


def test_list_and_get_project(client):
    store.save("demo", {"title": "Demo", "lyrics": {"lines": []}, "scenes": []})
    assert [p["id"] for p in client.get("/api/projects").json()] == ["demo"]
    assert client.get("/api/projects/demo").json()["title"] == "Demo"
    assert client.get("/api/projects/missing").status_code == 404


def test_put_rejects_stale_version(client):
    v = store.save("demo", {"title": "Demo", "lyrics": {"lines": []}, "scenes": []})
    ok = client.put(f"/api/projects/demo?base={v}", json={"title": "New", "lyrics": {"lines": []}, "scenes": []})
    assert ok.status_code == 200
    stale = client.put(f"/api/projects/demo?base={v}", json={"title": "Older edit", "lyrics": {"lines": []}, "scenes": []})
    assert stale.status_code == 409
    assert store.load("demo")["title"] == "New"


def test_put_recomputes_legacy_line_map(client):
    data = {
        "title": "Demo",
        "world": "legacy",
        "scenes": [],
        "legacy": {"origLines": ["Europa sagt:", "Dann geht es los"], "lineMap": ["l0", "l1"]},
        "lyrics": {"lines": [make_line("l0", "Europe sagt: Danach geht es los")]},
    }
    store.save("demo", data)
    r = client.put("/api/projects/demo", json=data).json()
    assert r["lineMap"] == [{"id": "l0", "from": 0, "to": 1}, {"id": "l0", "from": 2, "to": 5}]
    assert store.load("demo")["legacy"]["lineMap"] == r["lineMap"]


def test_legacy_page_gets_versioned_bundle_urls(client, projects):
    store.save("demo", {"title": "Demo"})
    legacy = projects / "demo" / "legacy"
    legacy.mkdir()
    (legacy / "index.html").write_text('<link href="app.css"><script src="app.js"></script>', encoding="utf-8")
    (legacy / "app.js").write_text("// bundle", encoding="utf-8")
    (legacy / "app.css").write_text("body{}", encoding="utf-8")
    r = client.get("/api/projects/demo/files/legacy/index.html")
    assert r.headers["cache-control"] == "no-store"
    assert '"app.js?v=' in r.text
    assert '"app.css?v=' in r.text
    js = client.get("/api/projects/demo/files/legacy/app.js")
    assert js.headers["cache-control"] == "no-store"
    assert js.text == "// bundle"


def test_missing_file_is_404(client):
    store.save("demo", {"title": "Demo"})
    assert client.get("/api/projects/demo/files/nope.txt").status_code == 404
