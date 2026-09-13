import hashlib
from rtve_rag.ingestion.models import DocumentMetadata, SubtitleChunk, SubtitleCue

def chunk_cues(cues:list[SubtitleCue], metadata:DocumentMetadata, chunk_size:int=800, overlap:int=120)->list[SubtitleChunk]:
    if chunk_size<=0 or not 0<=overlap<chunk_size: raise ValueError('Parámetros de chunking inválidos')
    result=[]; current=[]; size=0
    def emit():
        nonlocal current,size
        if not current:return
        text=' '.join(c.text for c in current); pos=len(result); digest=hashlib.sha256(text.encode()).hexdigest()[:12]
        result.append(SubtitleChunk(f'{metadata.document_id}_{pos:04d}_{digest}',text,current[0].start_ms,current[-1].end_ms,pos,metadata))
        kept=[]; kept_size=0
        for cue in reversed(current):
            kept.insert(0,cue); kept_size+=len(cue.text)+1
            if kept_size>=overlap: break
        current=kept; size=sum(len(c.text)+1 for c in current)
    for cue in cues:
        if current and size+len(cue.text)+1>chunk_size: emit()
        current.append(cue); size+=len(cue.text)+1
    emit(); return result
