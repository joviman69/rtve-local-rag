from pathlib import Path
import rtve_rag.ingestion.incremental as incremental


def subtitle(path: Path, text: str = "Hola") -> None:
    path.write_text(f"1\n00:00:00,000 --> 00:00:02,000\n{text}\n", encoding="utf-8")


def configure(monkeypatch):
    calls = {"embed": 0, "upsert": [], "deleted": []}
    monkeypatch.setattr(incremental, "embed", lambda texts, *_: calls.__setitem__("embed", calls["embed"] + 1) or [[0.1, 0.2] for _ in texts])
    monkeypatch.setattr(incremental, "ensure_collection", lambda *_: None)
    monkeypatch.setattr(incremental, "upsert_chunks", lambda _, __, chunks, ___: calls["upsert"].extend(chunks))
    monkeypatch.setattr(incremental, "delete_chunks", lambda _, __, ids: calls["deleted"].extend(ids))
    return calls


def run(path, state, monkeypatch, **kwargs):
    calls = configure(monkeypatch)
    report = incremental.run_incremental(path, {}, state, object(), "test", "url", "model", **kwargs)
    return report, calls


def test_indexes_new_file_and_writes_state(tmp_path, monkeypatch):
    path = tmp_path / "telediario-1_2026-09-04_1500_es.srt"; subtitle(path)
    report, calls = run(path, tmp_path / "state.json", monkeypatch)
    assert report["indexed_documents"] == 1 and report["indexed_chunks"] == 1
    assert calls["embed"] == 1 and calls["upsert"]


def test_skips_unchanged_file_without_embedding(tmp_path, monkeypatch):
    path = tmp_path / "telediario-1_2026-09-04_1500_es.srt"; subtitle(path)
    state = tmp_path / "state.json"; run(path, state, monkeypatch)
    report, calls = run(path, state, monkeypatch)
    assert report["skipped"] == 1 and calls["embed"] == 0


def test_dry_run_does_not_write_state_or_index(tmp_path, monkeypatch):
    path = tmp_path / "telediario-1_2026-09-04_1500_es.srt"; subtitle(path)
    state = tmp_path / "state.json"; report, calls = run(path, state, monkeypatch, dry_run=True)
    assert report["planned"] == 1 and not state.exists() and calls["embed"] == 0


def test_changed_file_replaces_obsolete_chunk_ids(tmp_path, monkeypatch):
    path = tmp_path / "telediario-1_2026-09-04_1500_es.srt"; subtitle(path, "Primera versión")
    state = tmp_path / "state.json"; run(path, state, monkeypatch)
    old_id = incremental.load_state(state)["documents"]["rtve_telediario-1_2026-09-04_1500_es"]["chunk_ids"][0]
    subtitle(path, "Versión modificada")
    report, calls = run(path, state, monkeypatch)
    assert report["updated"] == 1 and calls["deleted"] == [old_id]
