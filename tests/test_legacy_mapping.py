"""Mapping the lines of an imported (original) video engine onto the studio lyrics."""

from conftest import make_line
from studio.legacy import map_entry_id, norm, parse_raw, word_map


def test_identical_lines_map_one_to_one():
    lines = [make_line("l0", "Hello world"), make_line("l1", "Second line here")]
    assert word_map(["Hello world", "Second line here"], lines) == ["l0", "l1"]


def test_merged_studio_line_maps_to_word_ranges():
    lines = [make_line("l0", "Twenty thirty one is coming, and time doesn't wait.")]
    assert word_map(["Twenty thirty one is coming,", "and time doesn't wait."], lines) == [
        {"id": "l0", "from": 0, "to": 4},
        {"id": "l0", "from": 5, "to": 8},
    ]


def test_changed_words_stay_with_their_line():
    # "Europa" → "Europe", "Dann" → "Danach": the whole line must still be shown
    lines = [make_line("l0", "Europe sagt:"), make_line("l1", "Danach geht es los")]
    assert word_map(["Europa sagt:", "Dann geht es los"], lines) == ["l0", "l1"]


def test_line_no_longer_sung_maps_to_none():
    lines = [make_line("l0", "Keep this line")]
    assert word_map(["Keep this line", "Completely different words"], lines) == ["l0", None]


def test_map_entry_id_accepts_all_entry_kinds():
    assert map_entry_id("l3") == "l3"
    assert map_entry_id({"id": "l4", "from": 1, "to": 2}) == "l4"
    assert map_entry_id(None) is None


def test_norm_ignores_case_and_punctuation():
    assert norm("Doesn't!") == "doesnt"


def test_parse_raw_reads_old_lyrics_ts():
    ts = """
export const OTHER = 1;
const RAW: [string, string][] = [
  ['intro', 'Lights on'],
  ["verse1", "It's \\"quoted\\""], // comment
  ['chorus', 'Sing'],
];
const AFTER = [['x', 'not lyrics']];
"""
    assert parse_raw(ts) == [("intro", "Lights on"), ("verse1", 'It\'s "quoted"'), ("chorus", "Sing")]
