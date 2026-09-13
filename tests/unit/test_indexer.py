import json
from pathlib import Path
import pytest
from rtve_rag.ingestion.indexer import load_chunks

def test_load_chunks_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / 'empty.jsonl'; path.write_text('', encoding='utf-8')
    with pytest.raises(ValueError): load_chunks(path)

def test_load_chunks_reads_valid_jsonl(tmp_path: Path) -> None:
    path = tmp_path / 'chunks.jsonl'; path.write_text(json.dumps({'chunk_id':'one','text':'hola'})+'\n', encoding='utf-8')
    assert load_chunks(path)[0]['chunk_id'] == 'one'
