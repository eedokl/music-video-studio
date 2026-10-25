from studio.lyrics_text import parse, plain, section_of

LYRICS = """
[Intro]
Lights on

[Verse 1]
First verse line
(Robotic voice)

[Chorus]
Sing it loud
[Verse 2]
Second verse line
[Bridge]
Quiet now
[Final Chorus]
Sing it louder
[Outro]
Goodbye
"""


def test_parse_assigns_sections_and_drops_headers_and_stage_directions():
    rows = parse(LYRICS)
    assert [(r["section"], r["text"]) for r in rows] == [
        ("intro", "Lights on"),
        ("verse1", "First verse line"),
        ("chorus", "Sing it loud"),
        ("verse2", "Second verse line"),
        ("bridge", "Quiet now"),
        ("final", "Sing it louder"),
        ("outro", "Goodbye"),
    ]
    assert rows[2]["header"] == "[Chorus]"


def test_lines_before_any_header_are_verse1():
    assert parse("just a line\nanother")[0] == {"section": "verse1", "text": "just a line", "header": ""}


def test_section_of_aliases():
    assert section_of("[Refrain]", 1) == "chorus"
    assert section_of("[Hook]", 1) == "chorus"
    assert section_of("[Pre-Chorus]", 2) == "verse2"
    assert section_of("[Breakdown]", 1) == "bridge"
    assert section_of("[End]", 3) == "outro"


def test_plain_keeps_headers_once_per_block_and_round_trips():
    rows = parse(LYRICS)
    text = plain(rows)
    assert text.splitlines()[:4] == ["[Intro]", "Lights on", "[Verse 1]", "First verse line"]
    assert text.endswith("Goodbye\n")
    assert [r["text"] for r in parse(text)] == [r["text"] for r in rows]


def test_plain_without_header_writes_placeholder():
    assert plain(parse("a\nb")) == "[Verse]\na\nb\n"
