#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Descargador API-only de subtítulos de informativos RTVE Play.

No usa Playwright, Selenium, scraping HTML, sitemaps ni navegación de páginas
web. Todas las operaciones usan exclusivamente los endpoints JSON públicos de
la API de RTVE y las URLs de pista de subtítulos que la API devuelve.

Por defecto descarga sólo la edición de las 15 horas y genera, por cada SRT,
un TXT limpio con una frase por línea y sin líneas vacías.

Ejemplos:
  python rtve_subs_api_only.py --desde 2026-09-01 --hasta 2026-09-05
  python rtve_subs_api_only.py --programa telediario-2 --edicion 21 --desde 2026-09-01 --hasta 2026-09-05
  python rtve_subs_api_only.py --programa telediario-1 --todas-las-ediciones --desde 2026-09-01 --hasta 2026-09-05

Dependencia: pip install requests
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

APP_VERSION = "2.0.0-api-only"
API_HOSTS = ("https://api2.rtve.es", "https://api.rtve.es", "https://www.rtve.es")
PROGRAMS = {
    "telediario-1": "45030",
    "telediario-2": "45031",
    "telediario-matinal": "45032",
    "informe-semanal": "45680",
}
USER_AGENT = "rtve-subs-api-only/2.0 (uso personal; rate limited)"
LOG = logging.getLogger("rtve-subs")
TIME_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[,.]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[,.]\d{1,3})"
)

@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str

@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    emitted_at: datetime
    html_url: str
    program: str


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Usa fechas AAAA-MM-DD") from exc


def parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    for fmt in (
        "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text.replace("Z", "+0000"), fmt)
        except ValueError:
            pass
    return None


def seconds(timestamp: str) -> float:
    values = timestamp.replace(",", ".").split(":")
    if len(values) == 2:
        hours, minutes, secs = "0", values[0], values[1]
    else:
        hours, minutes, secs = values
    return int(hours) * 3600 + int(minutes) * 60 + float(secs)


def srt_time(value: float) -> str:
    milliseconds = round(max(value, 0) * 1000)
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def cue_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"<[^>]+>|\{\\[^}]*\}", "", value)
    return re.sub(r"\s+", " ", value.replace("\u200b", " ")).strip()


def parse_cues(source: str) -> list[Cue]:
    result: list[Cue] = []
    source = source.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    for block in re.split(r"\n[ \t]*\n", source):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines or lines[0].upper().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if index is None:
            continue
        found = TIME_RE.search(lines[index])
        if not found:
            continue
        text = cue_text(" ".join(lines[index + 1:]))
        if not text:
            continue
        try:
            start, end = seconds(found.group("start")), seconds(found.group("end"))
        except (ValueError, TypeError):
            continue
        if end >= start:
            if result and result[-1].text.casefold() == text.casefold():
                previous = result[-1]
                result[-1] = Cue(previous.start, max(previous.end, end), previous.text)
            else:
                result.append(Cue(start, end, text))
    return result


def normalized_srt(cues: list[Cue]) -> str:
    return "\n\n".join(
        f"{index}\n{srt_time(cue.start)} --> {srt_time(cue.end)}\n{cue.text}"
        for index, cue in enumerate(cues, 1)
    ) + "\n"


def clean_lines(cues: list[Cue]) -> list[str]:
    text = " ".join(cue.text for cue in cues)
    text = re.sub(r"\s+", " ", text).strip()
    return [line.strip() for line in re.split(r"(?<=[.!?…])\s+", text) if line.strip()]


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise

class RtveApi:
    def __init__(self, rps: float) -> None:
        retries = Retry(total=4, connect=4, read=4, backoff_factor=1, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(("GET",)))
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})
        self.rps = rps
        self.last_request = 0.0
        self.host = API_HOSTS[0]

    def get(self, path: str, *, params: Optional[dict[str, str]] = None, text: bool = False) -> Any:
        delay = (1 / self.rps) - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        errors: list[str] = []
        for host in (self.host,) + tuple(item for item in API_HOSTS if item != self.host):
            try:
                response = self.session.get(host + path, params=params, timeout=(10, 45))
                self.last_request = time.monotonic()
                response.raise_for_status()
                self.host = host
                if text:
                    return response.content.decode("utf-8-sig", errors="replace")
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{host}: {exc}")
        raise RuntimeError("API RTVE no disponible: " + " | ".join(errors))

    def subtitles(self, video_id: str) -> Optional[str]:
        payload = self.get(f"/api/videos/{video_id}/subtitulos.json")
        entries = ((payload.get("page") or {}).get("items") or [])
        for preferred in ("es", "es-es", "es_es"):
            for entry in entries:
                language = str(entry.get("lang") or "").casefold()
                source = str(entry.get("src") or "").strip()
                if language == preferred and source:
                    return "https:" + source if source.startswith("//") else source.replace("http://", "https://", 1)
        return None

    def subtitle_text(self, url: str) -> str:
        delay = (1 / self.rps) - (time.monotonic() - self.last_request)
        if delay > 0:
            time.sleep(delay)
        response = self.session.get(url, timeout=(10, 45))
        self.last_request = time.monotonic()
        response.raise_for_status()
        return response.content.decode("utf-8-sig", errors="replace")

    def videos(self, program_id: str, program: str, start: date, end: date) -> Iterator[Video]:
        seen: set[str] = set()
        for page in range(1, 201):
            payload = self.get(
                f"/api/programas/{program_id}/videos.json",
                params={"size": "60", "page": str(page), "fechaDesde": (start - timedelta(days=1)).strftime("%d-%m-%Y"), "fechaHasta": (end + timedelta(days=1)).strftime("%d-%m-%Y"), "lang": "es"},
            )
            page_data = payload.get("page") or {}
            entries = page_data.get("items") or []
            LOG.info("Catálogo página %s: %d elementos", page, len(entries))
            if not entries:
                break
            for raw in entries:
                video_id = str(raw.get("id") or "")
                emitted = parse_datetime(raw.get("dateOfEmission") or raw.get("publicationDate"))
                if not video_id.isdigit() or emitted is None or video_id in seen or not start <= emitted.date() <= end:
                    continue
                seen.add(video_id)
                yield Video(video_id, str(raw.get("longTitle") or raw.get("title") or ""), emitted, str(raw.get("htmlUrl") or ""), program)
            if page >= int(page_data.get("totalPages") or 999999):
                break

def matches_edition(video: Video, edition: Optional[int]) -> bool:
    if edition is None:
        return True
    return bool(re.search(rf"\b{edition}\s*horas\b", video.title.casefold())) or video.emitted_at.hour == edition

def filename(video: Video) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", video.program)
    return f"{safe}_{video.emitted_at:%Y-%m-%d}_{video.emitted_at:%H%M}_{video.video_id}_es"

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Descargador RTVE API-only: sin navegador ni scraping web.")
    parser.add_argument("--programa", choices=tuple(PROGRAMS), default="telediario-1")
    parser.add_argument("--program-id", default=None, help="ID API para uno de los programas admitidos")
    parser.add_argument("--desde", type=parse_date, required=True)
    parser.add_argument("--hasta", type=parse_date, required=True)
    parser.add_argument("--edicion", type=int, choices=(15, 21), default=15, help="Edición objetivo. Def: 15")
    parser.add_argument("--todas-las-ediciones", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("data/subtitles"))
    parser.add_argument("--clean-out", type=Path, default=None)
    parser.add_argument("--rps", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR"), default="INFO")
    return parser

def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
    if args.desde > args.hasta or args.rps <= 0:
        raise SystemExit("El rango de fechas o --rps no es válido")
    program_id = args.program_id or PROGRAMS[args.programa]
    edition = None if args.todas_las_ediciones else args.edicion
    api = RtveApi(args.rps)
    raw_root = args.out.expanduser().resolve()
    clean_root = args.clean_out.expanduser().resolve() if args.clean_out else raw_root.parent / "clean"
    LOG.info("=== rtve-subs %s | API-only ===", APP_VERSION)
    LOG.info("Programa %s (ID %s), edición %s", args.programa, program_id, edition or "todas")
    selected = [video for video in api.videos(program_id, args.programa, args.desde, args.hasta) if matches_edition(video, edition)]
    if not selected:
        LOG.warning("No se encontraron vídeos para los criterios indicados")
        return 2
    saved = skipped = errors = 0
    for video in sorted(selected, key=lambda item: item.emitted_at):
        stem = filename(video)
        raw_path = raw_root / f"{video.emitted_at:%Y/%m}" / f"{stem}.srt"
        clean_path = clean_root / f"{video.emitted_at:%Y/%m}" / f"{stem}.txt"
        if raw_path.exists() and clean_path.exists() and not args.force:
            LOG.info("↷ Ya existen: %s", raw_path.name); skipped += 1; continue
        LOG.info("[%s] %s", video.video_id, video.title)
        if args.dry_run:
            LOG.info("[dry-run] %s", raw_path); continue
        try:
            subtitle_url = api.subtitles(video.video_id)
            if not subtitle_url:
                LOG.warning("Sin subtítulos ES: %s", video.video_id); continue
            cues = parse_cues(api.subtitle_text(subtitle_url))
            if not cues:
                LOG.warning("Subtítulo sin cues analizables: %s", video.video_id); continue
            atomic_write(raw_path, normalized_srt(cues))
            atomic_write(clean_path, "\n".join(clean_lines(cues)) + "\n")
            LOG.info("✓ SRT y TXT: %s", raw_path.name); saved += 1
        except (RuntimeError, requests.RequestException, OSError) as exc:
            LOG.error("Error en %s: %s", video.video_id, exc); errors += 1
    LOG.info("Resumen: %d escritos | %d omitidos | %d errores", saved, skipped, errors)
    return 0 if saved or skipped else 2

if __name__ == "__main__":
    raise SystemExit(main())
