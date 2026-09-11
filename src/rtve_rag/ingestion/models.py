from dataclasses import asdict, dataclass
from typing import Any
@dataclass(frozen=True)
class SubtitleCue:
 start_ms:int; end_ms:int; text:str
@dataclass(frozen=True)
class DocumentMetadata:
 document_id:str; program:str; emission_date:str; language:str; original_format:str
@dataclass(frozen=True)
class SubtitleChunk:
 chunk_id:str; text:str; start_ms:int; end_ms:int; position:int; metadata:DocumentMetadata
 def payload(self)->dict[str,Any]:
  d=asdict(self.metadata); d.update({'chunk_id':self.chunk_id,'text':self.text,'start_ms':self.start_ms,'end_ms':self.end_ms,'position':self.position}); return d
