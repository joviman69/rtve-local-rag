import re
from pathlib import Path

from rtve_rag.ingestion.models import SubtitleCue

_TIMESTAMP = re.compile(r"(?P<start>(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{1,3})\s+-->\s+(?P<end>(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{1,3})")
_TAG = re.compile(r"<[^>]+>|\{\\[^}]*\}")


def timestamp_to_ms(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        parts = ["0", *parts]
    hours, minutes, seconds = parts
    second, _, millis = seconds.partition(".")
    return int(hours) * 3_600_000 + int(minutes) * 60_000 + int(second) * 1_000 + int((millis + "000")[:3])


def parse_subtitles(content: str) -> list[SubtitleCue]:
    lines = content.replace("\ufeff", "").replace("\r", "").splitlines()
    cues: list[SubtitleCue] = []
    index = 0
    while index < len(lines):
        match = _TIMESTAMP.search(lines[index])
        if match is None:
            index += 1
            continue
        index += 1
        text: list[str] = []
        while index < len(lines) and not _TIMESTAMP.search(lines[index]):
            line = lines[index].strip()
            index += 1
            if line and not line.isdigit() and not line.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
                text.append(line)
        normalized = re.sub(r"\s+", " ", _TAG.sub("", " ".join(text))).strip()
        if normalized:
            cues.append(SubtitleCue(timestamp_to_ms(match["start"]), timestamp_to_ms(match["end"]), normalized))
    return cues


def parse_subtitle_file(path: Path) -> list[SubtitleCue]:
    if path.suffix.lower() not in {".srt", ".vtt"}:
        raise ValueError(f"Formato no compatible: {path}")
    return parse_subtitles(path.read_text(encoding="utf-8-sig"))
