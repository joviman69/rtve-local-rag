from rtve_rag.ingestion.processor import parse_subtitles, timestamp_to_ms


def test_timestamp_to_ms() -> None:
    assert timestamp_to_ms("01:02.250") == 62_250
    assert timestamp_to_ms("01:01:02,250") == 3_662_250


def test_parser_preserves_times_and_removes_tags() -> None:
    cues = parse_subtitles("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n<i>Hola</i> mundo\n")
    assert len(cues) == 1
    assert cues[0] == type(cues[0])(1_000, 2_000, "Hola mundo")
