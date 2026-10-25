"""Export file handling: never overwrite, never leave a half-written file that looks finished."""

from studio.export import _free, _tmp, cleanup


def test_free_adds_counter_instead_of_overwriting(tmp_path):
    target = tmp_path / "Song.mp4"
    assert _free(target) == target
    target.write_bytes(b"x")
    (tmp_path / "Song (2).mp4").write_bytes(b"x")
    assert _free(target) == tmp_path / "Song (3).mp4"


def test_tmp_is_hidden_partial_next_to_final(tmp_path):
    assert _tmp(tmp_path / "Song mail.mp4") == tmp_path / ".Song mail.partial.mp4"


def test_cleanup_removes_only_leftovers(tmp_path):
    keep = [tmp_path / "Song.mp4", tmp_path / "Song (2).mp4"]
    junk = [tmp_path / ".Song.partial.mp4", tmp_path / ".pass_abc-0.log", tmp_path / ".demo-master.mp4"]
    for f in keep + junk:
        f.write_bytes(b"x")
    cleanup(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(f.name for f in keep)
