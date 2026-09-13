from pathlib import Path
from rtve_rag.ingestion.cli import subtitle_files

def test_subtitle_files_finds_supported_files_recursively_in_order(tmp_path: Path):
    (tmp_path / 'b.srt').write_text('', encoding='utf-8')
    nested = tmp_path / 'nested'
    nested.mkdir()
    (nested / 'a.vtt').write_text('', encoding='utf-8')
    (nested / 'ignore.txt').write_text('', encoding='utf-8')
    assert subtitle_files(tmp_path) == [tmp_path / 'b.srt', nested / 'a.vtt']
