import json
import logging

logger = logging.getLogger('rtve_rag')

def log_event(event: str, **fields: object) -> None:
    logger.info(json.dumps({'event': event, **fields}, ensure_ascii=False, default=str))
