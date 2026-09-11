import hashlib
from rtve_rag.ingestion.models import DocumentMetadata,SubtitleChunk,SubtitleCue
def chunk_cues(cues:list[SubtitleCue],metadata:DocumentMetadata,chunk_size:int=800,overlap:int=120)->list[SubtitleChunk]:
 chunks=[]; current=[]; size=0
 for cue in cues:
  if current and size+len(cue.text)+1>chunk_size:
   text=' '.join(x.text for x in current); chunks.append(SubtitleChunk(f'{metadata.document_id}_{len(chunks):04d}_{hashlib.sha256(text.encode()).hexdigest()[:12]}',text,current[0].start_ms,current[-1].end_ms,len(chunks),metadata)); current=[]; size=0
  current.append(cue); size+=len(cue.text)+1
 if current:
  text=' '.join(x.text for x in current); chunks.append(SubtitleChunk(f'{metadata.document_id}_{len(chunks):04d}_{hashlib.sha256(text.encode()).hexdigest()[:12]}',text,current[0].start_ms,current[-1].end_ms,len(chunks),metadata))
 return chunks
