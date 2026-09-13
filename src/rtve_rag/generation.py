import json
from urllib.request import Request, urlopen

def generate(prompt:str, base_url:str='http://localhost:11434', model:str='qwen3:8b')->str:
    request=Request(f'{base_url.rstrip("/")}/api/generate',data=json.dumps({'model':model,'prompt':prompt,'stream':False}).encode(),headers={'Content-Type':'application/json'},method='POST')
    with urlopen(request,timeout=180) as response: return json.loads(response.read())['response']
