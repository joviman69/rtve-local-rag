import json
from urllib.request import Request, urlopen

def generate(prompt:str, base_url:str='http://localhost:11434', model:str='qwen3:8b', response_format:str|None=None)->str:
    payload={'model':model,'prompt':prompt,'stream':False}
    if response_format: payload['format']=response_format
    request=Request(f'{base_url.rstrip("/")}/api/generate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=180) as response: return json.loads(response.read())['response']
