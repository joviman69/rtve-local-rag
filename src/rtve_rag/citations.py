def timestamp(ms:int|None)->str:
    if ms is None: return 'sin marca temporal'
    seconds=ms//1000
    return f'{seconds//60:02d}:{seconds%60:02d}'
def format_source(source:dict)->str:
    return f"{source.get('program','RTVE')} — {source.get('emission_date','sin fecha')} — {source.get('chunk_id','sin chunk')} — {timestamp(source.get('start_ms'))}"
def format_sources(sources:list[dict])->list[str]:
    return [format_source(source) for source in sources]
