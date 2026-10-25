"""'Audio aktualisieren': carry a storyboard over to a changed song."""

import pytest

from conftest import make_line
from studio.update import _time_map, merge, plan


def old_project():
    return {
        "lyrics": {"lines": [make_line("l0", "Hello world", 10), make_line("l1", "Second line", 12), make_line("l2", "Gone line", 14)]},
        "scenes": [{"id": "s0", "lines": ["l0", "l1", "l2"], "start": {"kind": "time", "t": 10.0}}],
        "events": [
            {"type": "flash", "at": {"kind": "word", "line": "l2", "word": 0}},
            {"type": "flash", "at": {"kind": "word", "line": "l0", "word": 1}},
        ],
        "title": "Song",
    }


def test_plan_matches_same_changed_new_and_removed_lines():
    info = plan(old_project(), [{"text": "Hello world"}, {"text": "Second lines"}, {"text": "Brand new thing"}])
    assert info == {"ids": ["l0", "l1", "l3"], "status": ["same", "changed", "new"], "removed": ["l2"]}


def test_time_map_follows_shifted_words():
    old = {"lyrics": {"lines": [make_line("l0", "a b c", 10, step=1)]}}
    new = {"lyrics": {"lines": [make_line("l0", "a b c", 12, step=1)]}}
    f, shift = _time_map(old, new)
    assert shift == pytest.approx(2.0)
    assert f(11) == pytest.approx(13)  # between words: interpolated
    assert f(100) == pytest.approx(102)  # after the last word: shifted
    assert f(0) == pytest.approx(0)  # the intro is stretched, 0:00 stays 0:00
    assert f(5) == pytest.approx(6)


def test_time_map_without_matches_is_identity():
    f, shift = _time_map({"lyrics": {"lines": []}}, {"lyrics": {"lines": []}})
    assert (f(42.0), shift) == (42.0, 0.0)


def test_merge_keeps_storyboard_and_places_new_lines():
    old = old_project()
    rows = [{"text": "Hello world"}, {"text": "Second lines"}, {"text": "Brand new thing"}]
    info = plan(old, rows)
    new = {"lyrics": {"lines": [make_line(lid, r["text"], 11 + 2 * k) for k, (lid, r) in enumerate(zip(info["ids"], rows, strict=True))]}}
    merge(old, new, info)
    scene = new["scenes"][0]
    assert scene["lines"] == ["l0", "l1", "l3"]  # removed line dropped, new line after its predecessor
    assert scene["start"] == {"kind": "time", "t": 11.0}  # time anchor follows the song
    assert [e["at"]["line"] for e in new["events"]] == ["l0"]  # event on the removed line is gone
    assert new["title"] == "Song"
    assert new["lastUpdate"]["added"] == [{"id": "l3", "text": "Brand new thing"}]
    assert new["lastUpdate"]["changed"] == [{"id": "l1", "text": "Second lines"}]
    assert new["lastUpdate"]["removed"] == [{"id": "l2", "text": "Gone line"}]
    assert old["scenes"][0]["lines"] == ["l0", "l1", "l2"]  # the old project is not modified
