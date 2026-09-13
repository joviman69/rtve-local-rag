import argparse
import json
from pathlib import Path
from rtve_rag.ingestion.chunker import chunk_cues
from rtve_rag.ingestion.metadata import load_manifest, metadata_from_path
from rtve_rag.ingestion.processor import parse_subtitle_file

def main()->None:
 parser=argparse.ArgumentParser(); parser.add_argument('--input',type=Path,required=True); parser.add_argument('--manifest',type=Path); parser.add_argument('--output',type=Path); parser.add_argument('--chunk-size',type=int,default=800); parser.add_argument('--overlap',type=int,default=120); args=parser.parse_args()
 metadata=metadata_from_path(args.input,load_manifest(args.manifest) if args.manifest else {}); output=args.output or Path('data/processed')/f'{metadata.document_id}.jsonl'; output.parent.mkdir(parents=True,exist_ok=True); output.write_text(''.join(json.dumps(c.payload(),ensure_ascii=False)+'\n' for c in chunk_cues(parse_subtitle_file(args.input),metadata,args.chunk_size,args.overlap)),encoding='utf-8')
if __name__=='__main__': main()
