import re
from rtve_rag.ingestion.models import SubtitleCue
TIME=re.compile(r'(?P<start>(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{1,3})\s+-->\s+(?P<end>(?:\d{1,2}:)?\d{2}:\d{2}[,.]\d{1,3})')
def ms(v:str)->int:
 p=v.replace(',','.').split(':'); p=['0',*p] if len(p)==2 else p; s,_,m=p[2].partition('.'); return int(p[0])*3600000+int(p[1])*60000+int(s)*1000+int((m+'000')[:3])
def parse_subtitles(content:str)->list[SubtitleCue]:
 lines=content.replace('\r','').splitlines(); out=[]; i=0
 while i<len(lines):
  match=TIME.search(lines[i])
  if not match: i+=1; continue
  i+=1; text=[]
  while i<len(lines) and not TIME.search(lines[i]):
   x=lines[i].strip(); i+=1
   if x and not x.isdigit(): text.append(x)
  x=re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',' '.join(text))).strip()
  if x: out.append(SubtitleCue(ms(match['start']),ms(match['end']),x))
 return out
