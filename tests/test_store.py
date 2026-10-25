import json

import pytest

from studio import store


def test_slug_handles_umlauts_and_symbols():
    assert store.slug("Größe & Ärger!") == "groesse-aerger"
    assert store.slug("!!!") == "song"


@pytest.mark.parametrize("pid", ["../evil", "Upper", "", "a/b", "-start"])
def test_project_dir_rejects_bad_ids(projects, pid):
    with pytest.raises(ValueError):
        store.project_dir(pid)


def test_new_id_avoids_existing_projects(projects):
    (projects / "my-song").mkdir()
    (projects / "my-song-2").mkdir()
    assert store.new_id("My Song") == "my-song-3"


def test_save_load_history_and_restore(projects):
    store.save("demo", {"title": "v1"})
    assert store.load("demo") == {"title": "v1"}
    assert store.history("demo") == []  # nothing to keep on the first save
    store.save("demo", {"title": "v2"})
    hist = store.history("demo")
    assert len(hist) == 1
    assert json.loads((projects / "demo" / ".history" / hist[0]).read_text(encoding="utf-8")) == {"title": "v1"}
    store.restore("demo", hist[0])
    assert store.load("demo") == {"title": "v1"}


def test_save_without_history(projects):
    store.save("demo", {"title": "v1"})
    store.save("demo", {"title": "v2"}, keep_history=False)
    assert store.history("demo") == []


def test_restore_rejects_paths(projects):
    store.save("demo", {"title": "v1"})
    with pytest.raises(FileNotFoundError):
        store.restore("demo", "../project.json")


def test_list_projects_skips_broken_files(projects):
    store.save("good", {"title": "Good", "audio": {"duration": 12.5}})
    (projects / "broken").mkdir()
    (projects / "broken" / "project.json").write_text("{not json", encoding="utf-8")
    (projects / "empty").mkdir()
    listed = store.list_projects()
    assert [(p["id"], p["title"], p["duration"]) for p in listed] == [("good", "Good", 12.5)]


def test_safe_file_stays_inside_project(projects):
    store.save("demo", {})
    assert store.safe_file("demo", "legacy/app.js") == (projects / "demo" / "legacy" / "app.js").resolve()
    for rel in ("../other/project.json", "../../secret.txt"):
        with pytest.raises(ValueError):
            store.safe_file("demo", rel)
