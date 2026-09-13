import argparse
import json
from pathlib import Path
from rtve_rag.ingestion.chunker import chunk_cues
from rtve_rag.ingestion.metadata import load_manifest, metadata_from_path
from rtve_rag.ingestion.processor import parse_subtitle_file

def subtitle_files(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() not in {'.srt', '.vtt'}:
            raise ValueError(f'Formato no compatible: {path}')
        return [path]
    if not path.is_dir():
        raise ValueError(f'Ruta de entrada no encontrada: {path}')
    files = sorted(file for file in path.rglob('*') if file.is_file() and file.suffix.lower() in {'.srt', '.vtt'})
    if not files:
        raise ValueError(f'No se encontraron archivos SRT o VTT en: {path}')
    return files

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--output')
    parser.add_argument('--chunk-size', type=int, default=800)
    parser.add_argument('--overlap', type=int, default=120)
    args = parser.parse_args()
    input_path = Path(args.input)
    files = subtitle_files(input_path)
    manifest = load_manifest(args.manifest) if args.manifest else {}
    payloads = []
    for file in files:
        metadata = metadata_from_path(file, manifest)
        payloads.extend(chunk.payload() for chunk in chunk_cues(parse_subtitle_file(file), metadata, args.chunk_size, args.overlap))
    output = Path(args.output) if args.output else (Path('data/processed/chunks.jsonl') if input_path.is_dir() else Path('data/processed') / f'{metadata_from_path(files[0], manifest).document_id}.jsonl')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(''.join(json.dumps(payload, ensure_ascii=False) + '\n' for payload in payloads), encoding='utf-8')
    print(json.dumps({'input_files': len(files), 'chunks': len(payloads), 'output': str(output)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
