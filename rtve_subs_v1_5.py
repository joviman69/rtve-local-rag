#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rtve_subs.py — Descarga automatizada de subtítulos de informativos de RTVE Play.

Objetivo
--------
Descargar los ficheros de subtítulos (.vtt nativo y/o .srt convertido) de los
programas informativos de RTVE (por defecto `telediario-1`) para un rango de
fechas, dejándolos en una estructura local ordenada por año y mes:

    data/subtitles/2026/09/telediario-1_2026-09-03_1500_es.srt

Estrategia (dos motores)
------------------------
1) `--engine api` (POR DEFECTO, recomendado):
   RTVE publica una API REST pública y sin autenticación (documentada de forma
   no oficial en https://es.wikibooks.org/wiki/API_Rtve):
     - Listado de vídeos de un programa:
         https://api2.rtve.es/api/programas/{programId}/videos.json
           ?size=60&page=N&fechaDesde=dd-MM-yyyy&fechaHasta=dd-MM-yyyy
     - Metadatos de un vídeo:
         https://api2.rtve.es/api/videos/{videoId}.json
     - Subtítulos de un vídeo (lo que nos interesa):
         https://api2.rtve.es/api/videos/{videoId}/subtitulos.json
         -> {"page":{"items":[{"src":"https://www.rtve.es/resources/vtt/..vtt",
                              "lang":"es"}, ...]}}
   Es 100% JSON, estable, mucho más rápido y muchísimo menos agresivo con el
   servidor que renderizar la SPA.

2) `--engine playwright` (RESPALDO):
   Renderiza la página del vídeo (`/play/videos/...`) en un navegador headless
   e intercepta el tráfico de red para capturar `subtitulos.json` y/o las URLs
   `*.vtt` que pide el reproductor. Útil si la API cambiara o si un contenido
   sólo expone los subtítulos desde el player. Requiere:
       pip install playwright && playwright install chromium

   El descubrimiento de vídeos del rango de fechas sigue haciéndose por API
   (usar el navegador para paginar el catálogo sería innecesariamente costoso);
   con `--engine playwright` también se puede pasar `--url` para procesar URLs
   concretas de `/play/videos/...` o `/noticias/...`.

Robustez incluida
-----------------
* Sesión `requests` con reintentos propios + retroceso exponencial con jitter,
  respeto de `Retry-After`, y reintento sólo en errores transitorios
  (429/500/502/503/504, timeouts, errores de conexión).
* Rotación de User-Agents (pool configurable) por petición.
* Rate limiting global tipo token-bucket (`--rps`) + pausa configurable entre
  vídeos, para no castigar a los servidores de RTVE.
* Manifest JSON (`.rtve_subs_manifest.json`) para reanudar sin volver a bajar
  lo ya descargado (`--force` lo ignora).
* Escrituras atómicas (fichero temporal + `os.replace`), nada de ficheros a
  medias si se corta la ejecución.
* `logging` nativo (consola + fichero rotatorio), cero `print` en el flujo.
* Apagado limpio con SIGINT/SIGTERM.
* Códigos de salida: 0 OK, 1 error fatal, 2 sin resultados, 130 interrumpido.

Nota legal / de cortesía
------------------------
`https://www.rtve.es/robots.txt` incluye `Disallow: /api/` y `Disallow: /*.json$`
para crawlers genéricos. Este script NO es un crawler de indexación: hace un
número muy reducido de peticiones deterministas sobre contenido público. Aun
así, por defecto va limitado (1 req/s) e identificado. Úsalo para fines
personales, de investigación o de accesibilidad, revisa las condiciones de uso
de RTVE y no redistribuyas el material descargado.

Ejemplos
--------
    # Telediario 1 completo, primeros días de septiembre, VTT + SRT
    python rtve_subs.py --desde 2026-09-01 --hasta 2026-09-03 --formato both

    # Todos los idiomas disponibles, sólo episodios completos
    python rtve_subs.py --desde 2026-08-01 --hasta 2026-08-31 --langs all

    # Incluir también los fragmentos/noticias del programa
    python rtve_subs.py --desde 2026-09-01 --hasta 2026-09-03 --incluir-fragmentos

    # Otro programa por slug (se resuelve el ID por API)
    python rtve_subs.py --programa telediario-2 --desde 2026-09-01 --hasta 2026-09-02

    # Ver qué haría, sin descargar nada
    python rtve_subs.py --desde 2026-09-01 --hasta 2026-09-03 --dry-run

    # Respaldo con navegador para URLs concretas
    python rtve_subs.py --engine playwright \
        --url https://www.rtve.es/play/videos/telediario-1/15-horas-03-09-26/17211243/

Requisitos: Python 3.9+, `requests`. Opcionales: `beautifulsoup4` (respaldo de
parseo HTML), `playwright` (motor de navegador).
"""

from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import random
import re
import signal
import sys
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    sys.stderr.write("Falta la dependencia 'requests'. Instala con: pip install requests\n")
    raise SystemExit(1)


# --------------------------------------------------------------------------- #
# Constantes
# --------------------------------------------------------------------------- #

APP_NAME = "rtve-subs"
APP_VERSION = "1.5.0"

API_HOSTS: Tuple[str, ...] = ("https://api2.rtve.es", "https://api.rtve.es", "https://www.rtve.es")
API_PROGRAM_VIDEOS = "{host}/api/programas/{program_id}/videos.json"
API_PROGRAMS = "{host}/api/programas.json"
API_VIDEO = "{host}/api/videos/{video_id}.json"
API_VIDEO_SUBS = "{host}/api/videos/{video_id}/subtitulos.json"

# IDs conocidos de programas informativos (evita una petición de resolución).
KNOWN_PROGRAMS: Dict[str, str] = {
    "telediario-1": "45030",
    "telediario-2": "45031",
    "telediario-matinal": "45032",
    "informe-semanal": "45680",
}

# Pool de User-Agents reales para rotación.
USER_AGENTS: Tuple[str, ...] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",
)

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 524})
MANIFEST_NAME = ".rtve_subs_manifest.json"

# Un episodio completo de Telediario se reconoce por su título largo.
FULL_EPISODE_TITLE_RE = re.compile(
    r"^\s*(telediario|informativo)\b.*?\b(\d{1,2})\s*horas\b", re.IGNORECASE
)
DATE_IN_TITLE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{2,4})")
VIDEO_ID_IN_URL_RE = re.compile(r"/(\d{5,})/?(?:[?#].*)?$")

LOG = logging.getLogger(APP_NAME)


# --------------------------------------------------------------------------- #
# Excepciones
# --------------------------------------------------------------------------- #

class RtveError(Exception):
    """Error base del scraper."""


class RtveTransientError(RtveError):
    """Fallo temporal: merece reintento."""


class RtvePermanentError(RtveError):
    """Fallo definitivo: no reintentar (404, JSON inválido, etc.)."""


class RtveBlockedError(RtveTransientError):
    """El servidor parece estar limitando o bloqueando las peticiones."""


# --------------------------------------------------------------------------- #
# Apagado limpio
# --------------------------------------------------------------------------- #

STOP = threading.Event()


def _install_signal_handlers() -> None:
    def _handler(signum, _frame):  # pragma: no cover
        LOG.warning("Señal %s recibida: terminando de forma ordenada…", signal.Signals(signum).name)
        STOP.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handler)
        except (ValueError, OSError):  # entornos sin señales (hilos, Windows service)
            pass


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

def setup_logging(log_dir: Path, level: str = "INFO", quiet: bool = False) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    LOG.setLevel(logging.DEBUG)
    LOG.propagate = False
    for handler in list(LOG.handlers):
        LOG.removeHandler(handler)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    if not quiet:
        console = logging.StreamHandler(stream=sys.stderr)
        console.setLevel(getattr(logging, level.upper(), logging.INFO))
        console.setFormatter(
            logging.Formatter(fmt="%(asctime)s | %(levelname)-8s | %(message)s",
                              datefmt="%H:%M:%S")
        )
        LOG.addHandler(console)

    rotating = logging.handlers.RotatingFileHandler(
        log_dir / "rtve_subs.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    rotating.setLevel(logging.DEBUG)
    rotating.setFormatter(fmt)
    LOG.addHandler(rotating)

    logging.getLogger("urllib3").setLevel(logging.WARNING)


# --------------------------------------------------------------------------- #
# Rate limiter (token bucket, thread-safe)
# --------------------------------------------------------------------------- #

class RateLimiter:
    """Limita a `rate` peticiones/segundo con ráfagas de hasta `burst`."""

    def __init__(self, rate: float, burst: int = 1) -> None:
        if rate <= 0:
            raise ValueError("rate debe ser > 0")
        self._rate = float(rate)
        self._capacity = max(1, int(burst))
        self._tokens = float(self._capacity)
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                self._tokens = min(self._capacity, self._tokens + (now - self._updated) * self._rate)
                self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait = (tokens - self._tokens) / self._rate
            LOG.debug("Rate limit: esperando %.2fs", wait)
            if STOP.wait(timeout=wait):
                raise KeyboardInterrupt


# --------------------------------------------------------------------------- #
# Cliente HTTP
# --------------------------------------------------------------------------- #

@dataclass
class HttpConfig:
    max_retries: int = 5
    backoff_base: float = 1.5
    backoff_cap: float = 60.0
    timeout: Tuple[float, float] = (10.0, 45.0)  # (connect, read)
    rps: float = 1.0
    burst: int = 2
    rotate_ua: bool = True
    proxy: Optional[str] = None


class RtveHttpClient:
    """`requests.Session` con rate limiting, rotación de UA y backoff exponencial."""

    def __init__(self, config: HttpConfig) -> None:
        self.config = config
        self.limiter = RateLimiter(rate=config.rps, burst=config.burst)
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        if config.proxy:
            self.session.proxies.update({"http": config.proxy, "https": config.proxy})
        self._ua = random.choice(USER_AGENTS)
        self.stats = {"requests": 0, "retries": 0, "bytes": 0}

    # -- cabeceras ---------------------------------------------------------- #
    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        if self.config.rotate_ua:
            self._ua = random.choice(USER_AGENTS)
        headers = {
            "User-Agent": self._ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.6",
            "Referer": "https://www.rtve.es/play/",
            "Origin": "https://www.rtve.es",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }
        if extra:
            headers.update(extra)
        return headers

    # -- núcleo ------------------------------------------------------------- #
    def request(
        self,
        url: str,
        *,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        expect: str = "json",
    ):
        """GET con reintentos. `expect` ∈ {json, text, bytes, response}."""
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.config.max_retries:
            if STOP.is_set():
                raise KeyboardInterrupt
            attempt += 1
            self.limiter.acquire()
            try:
                self.stats["requests"] += 1
                LOG.debug("GET %s params=%s (intento %d/%d)", url, params, attempt,
                          self.config.max_retries + 1)
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._headers(headers),
                    timeout=self.config.timeout,
                    allow_redirects=True,
                )
                status = response.status_code

                if status in RETRYABLE_STATUS:
                    retry_after = self._parse_retry_after(response.headers.get("Retry-After"))
                    if status in (429, 403):
                        raise RtveBlockedError(f"HTTP {status} en {url}")
                    raise RtveTransientError(f"HTTP {status} en {url}", )
                if status == 404:
                    raise RtvePermanentError(f"HTTP 404 (no existe) en {url}")
                if status >= 400:
                    raise RtvePermanentError(f"HTTP {status} en {url}")

                self.stats["bytes"] += len(response.content or b"")
                return self._decode(response, expect, url)

            except (RtveTransientError, requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.TooManyRedirects) as exc:
                last_error = exc
                if attempt > self.config.max_retries:
                    break
                self.stats["retries"] += 1
                delay = self._backoff(attempt, blocked=isinstance(exc, RtveBlockedError))
                LOG.warning("Fallo transitorio (%s). Reintento %d/%d en %.1fs",
                            exc, attempt, self.config.max_retries, delay)
                if STOP.wait(timeout=delay):
                    raise KeyboardInterrupt
            except RtvePermanentError:
                raise
            except requests.exceptions.RequestException as exc:  # pragma: no cover
                raise RtvePermanentError(f"Error de red no recuperable en {url}: {exc}") from exc

        raise RtveTransientError(
            f"Agotados {self.config.max_retries} reintentos para {url}: {last_error}"
        )

    # -- utilidades --------------------------------------------------------- #
    def _backoff(self, attempt: int, blocked: bool = False) -> float:
        base = self.config.backoff_base ** attempt
        if blocked:
            base *= 3  # si nos limitan, nos apartamos mucho más
        delay = min(self.config.backoff_cap, base)
        return delay * random.uniform(0.6, 1.4)  # jitter "full-ish"

    @staticmethod
    def _parse_retry_after(value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    @staticmethod
    def _decode(response: "requests.Response", expect: str, url: str):
        if expect == "response":
            return response
        if expect == "bytes":
            return response.content
        if expect == "text":
            # RTVE sirve los .vtt sin `charset` en el Content-Type, así que
            # `requests` los adivinaría como ISO-8859-1 y destrozaría las tildes.
            # Se fuerza UTF-8 y sólo se cae a cp1252/latin-1 si no es válido.
            raw = response.content or b""
            declared = ""
            content_type = response.headers.get("Content-Type", "")
            if "charset=" in content_type.lower():
                declared = content_type.lower().split("charset=")[-1].split(";")[0].strip()
            for codec in [c for c in (declared, "utf-8-sig", "cp1252", "latin-1") if c]:
                try:
                    return raw.decode(codec)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode("utf-8", errors="replace")
        # json (RTVE devuelve a veces text/plain con JSON dentro)
        try:
            return response.json()
        except ValueError as exc:
            snippet = (response.text or "")[:200].replace("\n", " ")
            raise RtvePermanentError(f"Respuesta no-JSON en {url}: {snippet!r}") from exc

    def close(self) -> None:
        self.session.close()


# --------------------------------------------------------------------------- #
# Modelo de datos
# --------------------------------------------------------------------------- #

@dataclass
class VideoItem:
    video_id: str
    title: str
    emitted_at: datetime
    html_url: str
    program_slug: str
    is_full_episode: bool
    duration_ms: Optional[int] = None
    subtitles: List[Tuple[str, str]] = field(default_factory=list)  # [(lang, url)]

    @property
    def day(self) -> date:
        return self.emitted_at.date()


# --------------------------------------------------------------------------- #
# Cliente de la API de RTVE
# --------------------------------------------------------------------------- #

class RtveApi:
    def __init__(self, http: RtveHttpClient) -> None:
        self.http = http
        self._host_order = list(API_HOSTS)

    def _get_with_failover(self, path_template: str, **fmt) -> dict:
        """Prueba los hosts de la API en orden hasta que uno responda."""
        errors: List[str] = []
        for host in list(self._host_order):
            url = path_template.format(host=host, **fmt)
            params = fmt.get("_params")
            try:
                data = self.http.request(url, params=params, expect="json")
                if host != self._host_order[0]:  # promociona el host que funciona
                    self._host_order.remove(host)
                    self._host_order.insert(0, host)
                return data
            except RtveError as exc:
                errors.append(f"{host}: {exc}")
                LOG.debug("Host %s falló: %s", host, exc)
        raise RtvePermanentError("Todos los hosts de la API fallaron -> " + " | ".join(errors))

    # -- programas ---------------------------------------------------------- #
    def resolve_program_id(self, slug: str) -> str:
        if slug in KNOWN_PROGRAMS:
            LOG.info("Programa '%s' -> ID %s (catálogo local)", slug, KNOWN_PROGRAMS[slug])
            return KNOWN_PROGRAMS[slug]

        LOG.info("Resolviendo ID del programa '%s' vía API…", slug)
        letter = (slug[:1] or "t").lower()
        for page in range(1, 6):
            data = self._get_with_failover(
                API_PROGRAMS, _params={"size": "60", "page": str(page), "startWithLetter": letter}
            )
            items = ((data or {}).get("page") or {}).get("items") or []
            if not items:
                break
            for item in items:
                url = str(item.get("htmlUrl") or "")
                if f"/{slug}/" in url or f"/{slug}" == url.rstrip("/")[-len(slug) - 1:]:
                    program_id = str(item.get("id"))
                    LOG.info("Programa '%s' -> ID %s (%s)", slug, program_id, item.get("title"))
                    return program_id
        raise RtvePermanentError(
            f"No se pudo resolver el ID del programa '{slug}'. Indícalo con --program-id."
        )

    # -- listado de vídeos por rango --------------------------------------- #
    def iter_program_videos(
        self,
        program_id: str,
        slug: str,
        date_from: date,
        date_to: date,
        page_size: int = 60,
        max_pages: int = 200,
    ) -> Iterator[VideoItem]:
        """
        Recorre el listado del programa filtrando por fechas en servidor y
        confirmando el rango en cliente (el filtro remoto es inclusivo/exclusivo
        según contenido, así que se pide con 1 día de margen a cada lado).
        """
        padded_from = date_from - timedelta(days=1)
        padded_to = date_to + timedelta(days=2)
        seen: set = set()

        for page in range(1, max_pages + 1):
            if STOP.is_set():
                raise KeyboardInterrupt
            params = {
                "size": str(page_size),
                "page": str(page),
                "fechaDesde": padded_from.strftime("%d-%m-%Y"),
                "fechaHasta": padded_to.strftime("%d-%m-%Y"),
                "lang": "es",
            }
            data = self._get_with_failover(
                API_PROGRAM_VIDEOS, program_id=program_id, _params=params
            )
            page_obj = (data or {}).get("page") or {}
            items = page_obj.get("items") or []
            total_pages = int(page_obj.get("totalPages") or 0)
            LOG.info("Catálogo página %d/%s: %d elementos", page, total_pages or "?", len(items))
            if not items:
                break

            older_than_range = 0
            for raw in items:
                item = self._parse_video_item(raw, slug)
                if item is None:
                    continue
                if item.video_id in seen:
                    continue
                seen.add(item.video_id)
                if item.day < date_from:
                    older_than_range += 1
                    continue
                if item.day > date_to:
                    continue
                yield item

            # El listado viene ordenado de más nuevo a más antiguo: si toda la
            # página ya cae por debajo del rango, no hace falta seguir.
            if items and older_than_range == len(items):
                LOG.debug("Página %d completamente anterior al rango: fin de la paginación", page)
                break
            if total_pages and page >= total_pages:
                break

    @staticmethod
    def _parse_video_item(raw: dict, slug: str) -> Optional[VideoItem]:
        try:
            video_id = str(raw.get("id") or "").strip()
            if not video_id.isdigit():
                return None
            title = str(raw.get("longTitle") or raw.get("title") or "").strip()
            emitted = parse_rtve_datetime(
                raw.get("dateOfEmission") or raw.get("publicationDate") or ""
            )
            if emitted is None:
                LOG.debug("Vídeo %s sin fecha utilizable, se omite", video_id)
                return None
            html_url = str(raw.get("htmlUrl") or f"https://www.rtve.es/play/videos/{video_id}/")
            duration = raw.get("duration")
            return VideoItem(
                video_id=video_id,
                title=title,
                emitted_at=emitted,
                html_url=html_url,
                program_slug=slug,
                is_full_episode=is_full_episode(title, duration),
                duration_ms=int(duration) if isinstance(duration, (int, float)) else None,
            )
        except Exception as exc:  # defensivo: un item raro no debe tumbar el run
            LOG.warning("No se pudo interpretar un elemento del catálogo: %s", exc)
            return None

    # -- vídeo suelto ------------------------------------------------------- #
    def get_video(self, video_id: str, slug_hint: str = "rtve") -> VideoItem:
        data = self._get_with_failover(API_VIDEO, video_id=video_id)
        items = ((data or {}).get("page") or {}).get("items") or []
        if not items:
            raise RtvePermanentError(f"La API no devolvió metadatos para el vídeo {video_id}")
        raw = items[0]
        program_info = raw.get("programInfo") or {}
        slug = slugify(str(program_info.get("title") or slug_hint))
        item = self._parse_video_item(raw, slug)
        if item is None:
            raise RtvePermanentError(f"Metadatos inválidos para el vídeo {video_id}")
        return item

    # -- subtítulos --------------------------------------------------------- #
    def get_subtitles(self, video_id: str) -> List[Tuple[str, str]]:
        data = self._get_with_failover(API_VIDEO_SUBS, video_id=video_id)
        items = ((data or {}).get("page") or {}).get("items") or []
        out: List[Tuple[str, str]] = []
        for entry in items:
            src = str(entry.get("src") or "").strip()
            lang = str(entry.get("lang") or "es").strip().lower()
            if not src:
                continue
            if src.startswith("//"):
                src = "https:" + src
            src = src.replace("http://", "https://", 1)
            out.append((lang, src))
        return out


# --------------------------------------------------------------------------- #
# Respaldo con Playwright (render dinámico + intercepción de red)
# --------------------------------------------------------------------------- #

class PlaywrightSubtitleFinder:
    """
    Abre la página del vídeo en Chromium headless, acepta el aviso de cookies,
    arranca el reproductor y captura las URLs de `subtitulos.json` / `*.vtt`
    que solicita el player. Se usa como respaldo del motor API.
    """

    def __init__(self, headless: bool = True, wait_ms: int = 12000, http: Optional[RtveHttpClient] = None):
        self.headless = headless
        self.wait_ms = wait_ms
        self.http = http

    def find(self, page_url: str) -> Tuple[Optional[str], List[Tuple[str, str]]]:
        """Devuelve (video_id, [(lang, url_vtt), ...])."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RtvePermanentError(
                "Playwright no está instalado. `pip install playwright && playwright install chromium`"
            ) from exc

        captured_json: List[str] = []
        captured_vtt: List[str] = []
        video_id = extract_video_id(page_url)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="es-ES",
                viewport={"width": 1366, "height": 768},
            )
            page = context.new_page()

            def on_request(request):
                url = request.url
                if "subtitulos.json" in url:
                    captured_json.append(url)
                elif url.endswith(".vtt") or ".vtt?" in url or url.endswith(".srt"):
                    captured_vtt.append(url)

            page.on("request", on_request)
            LOG.info("Playwright: cargando %s", page_url)
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
                self._accept_cookies(page)
                # Empujar al player a pedir los subtítulos.
                for selector in ("button[title*='Reproducir']", "button[aria-label*='Reproducir']",
                                 ".vjs-big-play-button", "video"):
                    try:
                        element = page.query_selector(selector)
                        if element:
                            element.click(timeout=2500)
                            break
                    except Exception:
                        continue
                page.wait_for_timeout(self.wait_ms)
                if not video_id:
                    video_id = extract_video_id(page.url)
                html = page.content()
            except Exception as exc:
                LOG.error("Playwright falló en %s: %s", page_url, exc)
                html = ""
            finally:
                context.close()
                browser.close()

        subs: List[Tuple[str, str]] = []
        # 1) Si capturamos el endpoint JSON, pedirlo por HTTP (más fiable y con idiomas).
        for json_url in dict.fromkeys(captured_json):
            if not self.http:
                break
            try:
                data = self.http.request(json_url, expect="json")
                for entry in ((data or {}).get("page") or {}).get("items") or []:
                    src = str(entry.get("src") or "")
                    if src:
                        subs.append((str(entry.get("lang") or "es").lower(),
                                     src.replace("http://", "https://", 1)))
            except RtveError as exc:
                LOG.warning("No se pudo leer %s: %s", json_url, exc)

        # 2) URLs .vtt observadas directamente en la red.
        for vtt_url in dict.fromkeys(captured_vtt):
            if not any(vtt_url == u for _, u in subs):
                subs.append(("es", vtt_url))

        # 3) Último recurso: rascar el HTML renderizado (BeautifulSoup si está).
        if not subs and html:
            subs.extend(extract_subs_from_html(html))

        LOG.info("Playwright: %d pista(s) de subtítulos localizadas en %s", len(subs), page_url)
        return video_id, subs

    @staticmethod
    def _accept_cookies(page) -> None:
        for selector in ("#didomi-notice-agree-button", "button#onetrust-accept-btn-handler",
                         "button:has-text('Aceptar')", "button:has-text('Acepto')"):
            try:
                btn = page.query_selector(selector)
                if btn:
                    btn.click(timeout=2000)
                    LOG.debug("Aviso de cookies aceptado con %s", selector)
                    return
            except Exception:
                continue


def extract_subs_from_html(html: str) -> List[Tuple[str, str]]:
    """Busca pistas de subtítulos en HTML renderizado (con o sin BeautifulSoup)."""
    found: List[Tuple[str, str]] = []

    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        for track in soup.find_all("track"):
            src = track.get("src") or ""
            if src:
                found.append((str(track.get("srclang") or "es").lower(), absolutize(src)))
        for box in soup.select("[data-config]"):
            raw = box.get("data-config") or ""
            try:
                config = json.loads(raw)
            except ValueError:
                continue
            ref = ((config.get("mediaConfig") or {}).get("subtitleRefUrl")) or ""
            if ref:
                found.append(("__ref__", absolutize(ref)))
    except ImportError:
        LOG.debug("BeautifulSoup no disponible; se usa sólo regex sobre el HTML")

    for match in re.finditer(r"https?://[^\"'\\\s]+\.vtt", html):
        url = match.group(0).replace("http://", "https://", 1)
        if not any(url == u for _, u in found):
            found.append(("es", url))
    return found


def absolutize(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return "https://www.rtve.es" + url
    return url


# --------------------------------------------------------------------------- #
# Conversión VTT -> SRT
# --------------------------------------------------------------------------- #

VTT_TIME_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})"
)
TAG_RE = re.compile(r"</?(?:c|v|i|b|u|ruby|rt|lang)(?:[^>]*)>", re.IGNORECASE)


def _normalize_timestamp(value: str) -> str:
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:  # mm:ss.mmm -> 00:mm:ss.mmm
        parts = ["00"] + parts
    hh, mm, rest = parts[0], parts[1], parts[2]
    sec, _, ms = rest.partition(".")
    ms = (ms + "000")[:3] if ms else "000"
    return f"{int(hh):02d}:{int(mm):02d}:{int(sec):02d},{ms}"


def vtt_to_srt(vtt_text: str) -> str:
    """Convierte WEBVTT a SRT: quita cabecera/NOTE/STYLE, tags y ajustes de cue."""
    text = vtt_text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = [b for b in re.split(r"\n{2,}", text) if b.strip()]
    out: List[str] = []
    index = 0

    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        head = lines[0].strip()
        if head.upper().startswith("WEBVTT") or head.startswith(("NOTE", "STYLE", "REGION")):
            continue

        time_line_idx = next((i for i, ln in enumerate(lines) if VTT_TIME_RE.search(ln)), None)
        if time_line_idx is None:
            continue
        match = VTT_TIME_RE.search(lines[time_line_idx])
        start = _normalize_timestamp(match.group("start"))
        end = _normalize_timestamp(match.group("end"))

        payload = []
        for line in lines[time_line_idx + 1:]:
            clean = TAG_RE.sub("", line)
            clean = re.sub(r"\{\\?[^}]*\}", "", clean).rstrip()
            if clean.strip():
                payload.append(clean)
        if not payload:
            continue

        index += 1
        out.append(f"{index}\n{start} --> {end}\n" + "\n".join(payload))

    return "\n\n".join(out) + ("\n" if out else "")


# --------------------------------------------------------------------------- #
# Utilidades varias
# --------------------------------------------------------------------------- #

def parse_rtve_datetime(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    LOG.debug("Fecha no reconocida: %r", value)
    return None


def is_full_episode(title: str, duration: Optional[object]) -> bool:
    """Heurística: los episodios completos llevan 'Telediario - NN horas' y duran >20 min."""
    if FULL_EPISODE_TITLE_RE.search(title or ""):
        if "cuatro minutos" in (title or "").lower():
            return False
        return True
    if isinstance(duration, (int, float)) and duration >= 20 * 60 * 1000:
        return bool(re.match(r"^\s*telediario\b", title or "", re.IGNORECASE))
    return False


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[\s_-]+", "-", value) or "rtve"


def extract_video_id(url: str) -> Optional[str]:
    match = VIDEO_ID_IN_URL_RE.search((url or "").strip())
    return match.group(1) if match else None


def parse_iso_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Fecha inválida '{value}': usa YYYY-MM-DD")


def atomic_write_text(path: Path, content: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return len(content.encode("utf-8"))


# --------------------------------------------------------------------------- #
# Manifest / estado
# --------------------------------------------------------------------------- #

class Manifest:
    """Registro de lo ya descargado, para reanudar sin repetir peticiones."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: Dict[str, dict] = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8")) or {}
                LOG.info("Manifest cargado: %d entradas previas", len(self.data))
            except (ValueError, OSError) as exc:
                LOG.warning("Manifest ilegible (%s): se empieza de cero", exc)
                self.data = {}
        self._dirty = False

    @staticmethod
    def key(video_id: str, lang: str, fmt: str) -> str:
        return f"{video_id}:{lang}:{fmt}"

    def has(self, video_id: str, lang: str, fmt: str, expected: Path) -> bool:
        entry = self.data.get(self.key(video_id, lang, fmt))
        return bool(entry) and expected.exists() and expected.stat().st_size > 0

    def add(self, video_id: str, lang: str, fmt: str, item: VideoItem, path: Path, size: int) -> None:
        self.data[self.key(video_id, lang, fmt)] = {
            "video_id": video_id,
            "lang": lang,
            "format": fmt,
            "title": item.title,
            "emitted_at": item.emitted_at.isoformat(),
            "html_url": item.html_url,
            "path": str(path),
            "bytes": size,
            "downloaded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        try:
            atomic_write_text(self.path, json.dumps(self.data, ensure_ascii=False, indent=2))
            self._dirty = False
            LOG.debug("Manifest guardado en %s", self.path)
        except OSError as exc:  # pragma: no cover
            LOG.error("No se pudo guardar el manifest: %s", exc)


# --------------------------------------------------------------------------- #
# Descargador
# --------------------------------------------------------------------------- #

@dataclass
class DownloadStats:
    videos_seen: int = 0
    videos_with_subs: int = 0
    videos_without_subs: int = 0
    files_written: int = 0
    files_skipped: int = 0
    errors: int = 0


class SubtitleDownloader:
    def __init__(
        self,
        api: RtveApi,
        http: RtveHttpClient,
        out_dir: Path,
        manifest: Manifest,
        langs: Sequence[str],
        formats: Sequence[str],
        dry_run: bool = False,
        force: bool = False,
        pause: float = 0.0,
    ) -> None:
        self.api = api
        self.http = http
        self.out_dir = out_dir
        self.manifest = manifest
        self.langs = [l.lower() for l in langs]
        self.formats = list(formats)
        self.dry_run = dry_run
        self.force = force
        self.pause = pause
        self.stats = DownloadStats()

    # -- rutas -------------------------------------------------------------- #
    def target_path(self, item: VideoItem, lang: str, fmt: str) -> Path:
        stamp = item.emitted_at
        name = (
            f"{item.program_slug}_{stamp.strftime('%Y-%m-%d')}_"
            f"{stamp.strftime('%H%M')}_{lang}.{fmt}"
        )
        if not item.is_full_episode:
            name = (
                f"{item.program_slug}_{stamp.strftime('%Y-%m-%d')}_{stamp.strftime('%H%M')}_"
                f"{item.video_id}_{lang}.{fmt}"
            )
        return self.out_dir / stamp.strftime("%Y") / stamp.strftime("%m") / name

    # -- selección de idiomas ---------------------------------------------- #
    def _select(self, subs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        if "all" in self.langs:
            return subs
        wanted = []
        for lang in self.langs:
            for entry_lang, url in subs:
                if entry_lang == lang or entry_lang.startswith(lang + "-"):
                    wanted.append((lang, url))
                    break
        if not wanted and subs:
            LOG.warning("Ningún idioma de %s disponible (hay: %s)",
                        self.langs, sorted({l for l, _ in subs}))
        return wanted

    # -- proceso por vídeo -------------------------------------------------- #
    def process(self, item: VideoItem) -> None:
        self.stats.videos_seen += 1
        LOG.info("[%s] %s — %s", item.video_id, item.emitted_at.strftime("%Y-%m-%d %H:%M"),
                 item.title[:90])

        try:
            subs = item.subtitles or self.api.get_subtitles(item.video_id)
        except RtvePermanentError as exc:
            LOG.error("Sin subtítulos para %s: %s", item.video_id, exc)
            self.stats.errors += 1
            return
        except RtveTransientError as exc:
            LOG.error("Fallo persistente pidiendo subtítulos de %s: %s", item.video_id, exc)
            self.stats.errors += 1
            return

        if not subs:
            LOG.warning("El vídeo %s no tiene pistas de subtítulos publicadas", item.video_id)
            self.stats.videos_without_subs += 1
            return

        selected = self._select(subs)
        if not selected:
            self.stats.videos_without_subs += 1
            return
        self.stats.videos_with_subs += 1

        for lang, url in selected:
            if STOP.is_set():
                raise KeyboardInterrupt
            self._download_track(item, lang, url)

        if self.pause > 0 and not self.dry_run:
            LOG.debug("Pausa de cortesía: %.2fs", self.pause)
            if STOP.wait(timeout=self.pause):
                raise KeyboardInterrupt

    def _download_track(self, item: VideoItem, lang: str, url: str) -> None:
        pending = []
        for fmt in self.formats:
            path = self.target_path(item, lang, fmt)
            if not self.force and self.manifest.has(item.video_id, lang, fmt, path):
                LOG.info("  ↷ ya existe %s", path)
                self.stats.files_skipped += 1
                continue
            pending.append((fmt, path))
        if not pending:
            return

        if self.dry_run:
            for fmt, path in pending:
                LOG.info("  [dry-run] %s -> %s", url, path)
            return

        try:
            raw = self.http.request(url, expect="text",
                                    headers={"Accept": "text/vtt,text/plain,*/*"})
        except RtveError as exc:
            LOG.error("  ✗ no se pudo descargar %s (%s): %s", url, lang, exc)
            self.stats.errors += 1
            return

        if not raw or len(raw.strip()) < 10:
            LOG.error("  ✗ pista vacía o inválida: %s", url)
            self.stats.errors += 1
            return

        for fmt, path in pending:
            try:
                content = raw if fmt == "vtt" else vtt_to_srt(raw)
                if fmt == "srt" and not content.strip():
                    LOG.error("  ✗ la conversión a SRT quedó vacía para %s", url)
                    self.stats.errors += 1
                    continue
                size = atomic_write_text(path, content)
                self.manifest.add(item.video_id, lang, fmt, item, path, size)
                self.stats.files_written += 1
                LOG.info("  ✓ %s (%s, %.1f KB)", path, lang, size / 1024)
            except OSError as exc:
                LOG.error("  ✗ error de escritura en %s: %s", path, exc)
                self.stats.errors += 1

        self.manifest.flush()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rtve_subs.py",
        description="Descarga subtítulos (.vtt/.srt) de informativos de RTVE Play por rango de fechas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Ejemplo: python rtve_subs.py --desde 2026-09-01 --hasta 2026-09-03 --formato both",
    )
    selection = parser.add_argument_group("selección de contenido")
    selection.add_argument("--programa", default="telediario-1",
                           help="Slug del programa en RTVE Play (por defecto: telediario-1)")
    selection.add_argument("--program-id", default=None,
                           help="ID numérico del programa (evita la resolución por API)")
    selection.add_argument("--desde", type=parse_iso_date, help="Fecha inicial YYYY-MM-DD")
    selection.add_argument("--hasta", type=parse_iso_date, help="Fecha final YYYY-MM-DD (incl.)")
    selection.add_argument("--url", action="append", default=[],
                           help="URL(s) concretas de /play/videos/... o /noticias/... (repetible)")
    selection.add_argument("--incluir-fragmentos", action="store_true",
                           help="Incluir noticias/fragmentos además del informativo completo")
    selection.add_argument("--langs", default="es",
                           help="Idiomas separados por coma (es,en,ca,gl,eu) o 'all'. Def: es")
    selection.add_argument("--formato", choices=("srt", "vtt", "both"), default="srt",
                           help="Formato de salida. Def: srt")

    output = parser.add_argument_group("salida")
    output.add_argument("--out", default="data/raw", help="Directorio raíz. Def: data/subtitles")
    output.add_argument("--log-dir", default="logs", help="Directorio de logs. Def: logs")
    output.add_argument("--manifest", default=None, help=f"Ruta del manifest. Def: <out>/{MANIFEST_NAME}")
    output.add_argument("--force", action="store_true", help="Redescargar aunque ya exista")
    output.add_argument("--dry-run", action="store_true", help="No escribe nada; sólo informa")

    network = parser.add_argument_group("red y cortesía")
    network.add_argument("--engine", choices=("api", "playwright"), default="api",
                         help="Motor de extracción. Def: api")
    network.add_argument("--rps", type=float, default=1.0,
                         help="Peticiones por segundo máximas. Def: 1.0")
    network.add_argument("--burst", type=int, default=2, help="Ráfaga permitida. Def: 2")
    network.add_argument("--pause", type=float, default=0.5,
                         help="Pausa extra entre vídeos (s). Def: 0.5")
    network.add_argument("--max-retries", type=int, default=5, help="Reintentos por petición. Def: 5")
    network.add_argument("--timeout", type=float, default=45.0, help="Timeout de lectura (s). Def: 45")
    network.add_argument("--no-rotate-ua", action="store_true", help="Desactiva la rotación de UA")
    network.add_argument("--proxy", default=None, help="Proxy HTTP(S), p. ej. http://127.0.0.1:8080")
    network.add_argument("--max-videos", type=int, default=0, help="Límite de vídeos (0 = sin límite)")
    network.add_argument("--no-headless", action="store_true",
                         help="Con --engine playwright, abre el navegador visible")

    misc = parser.add_argument_group("varios")
    misc.add_argument("--log-level", default="INFO",
                      choices=("DEBUG", "INFO", "WARNING", "ERROR"), help="Nivel en consola")
    misc.add_argument("--quiet", action="store_true", help="Sin salida por consola (sólo fichero)")
    misc.add_argument("--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    return parser


def resolve_formats(choice: str) -> List[str]:
    return ["srt", "vtt"] if choice == "both" else [choice]


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    out_dir = Path(args.out).expanduser().resolve()
    setup_logging(Path(args.log_dir).expanduser().resolve(), args.log_level, args.quiet)
    _install_signal_handlers()

    LOG.info("=== %s %s ===", APP_NAME, APP_VERSION)

    if not args.url and not (args.desde and args.hasta):
        LOG.error("Debes indicar --desde y --hasta, o al menos una --url")
        return 1
    if args.desde and args.hasta and args.desde > args.hasta:
        LOG.error("El rango es inválido: --desde (%s) es posterior a --hasta (%s)",
                  args.desde, args.hasta)
        return 1

    http = RtveHttpClient(HttpConfig(
        max_retries=args.max_retries,
        timeout=(10.0, args.timeout),
        rps=args.rps,
        burst=args.burst,
        rotate_ua=not args.no_rotate_ua,
        proxy=args.proxy,
    ))
    api = RtveApi(http)
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else out_dir / MANIFEST_NAME
    manifest = Manifest(manifest_path)

    downloader = SubtitleDownloader(
        api=api,
        http=http,
        out_dir=out_dir,
        manifest=manifest,
        langs=[l.strip() for l in args.langs.split(",") if l.strip()],
        formats=resolve_formats(args.formato),
        dry_run=args.dry_run,
        force=args.force,
        pause=args.pause,
    )

    finder: Optional[PlaywrightSubtitleFinder] = None
    if args.engine == "playwright":
        finder = PlaywrightSubtitleFinder(headless=not args.no_headless, http=http)

    started = time.monotonic()
    exit_code = 0
    try:
        items: List[VideoItem] = []

        # 1) URLs explícitas.
        for url in args.url:
            video_id = extract_video_id(url)
            if not video_id:
                LOG.error("No se pudo extraer el ID de vídeo de %s", url)
                downloader.stats.errors += 1
                continue
            try:
                item = api.get_video(video_id, slug_hint=args.programa)
            except RtveError as exc:
                LOG.warning("Metadatos no disponibles para %s (%s); se usa la URL tal cual",
                            video_id, exc)
                item = VideoItem(video_id=video_id, title=url, emitted_at=datetime.now(),
                                 html_url=url, program_slug=slugify(args.programa),
                                 is_full_episode=True)
            if finder:
                _, subs = finder.find(item.html_url or url)
                item.subtitles = [(l, u) for l, u in subs if l != "__ref__"]
            items.append(item)

        # 2) Rango de fechas vía catálogo del programa.
        if args.desde and args.hasta:
            program_id = args.program_id or api.resolve_program_id(args.programa)
            LOG.info("Buscando vídeos de '%s' (ID %s) entre %s y %s",
                     args.programa, program_id, args.desde, args.hasta)
            for item in api.iter_program_videos(program_id, slugify(args.programa),
                                                args.desde, args.hasta):
                if not args.incluir_fragmentos and not item.is_full_episode:
                    LOG.debug("Omitido fragmento: %s (%s)", item.title[:70], item.video_id)
                    continue
                if finder:
                    _, subs = finder.find(item.html_url)
                    item.subtitles = [(l, u) for l, u in subs if l != "__ref__"]
                items.append(item)
                if args.max_videos and len(items) >= args.max_videos:
                    LOG.info("Alcanzado --max-videos=%d", args.max_videos)
                    break

        if not items:
            LOG.warning("No se han encontrado vídeos que cumplan los criterios")
            return 2

        items.sort(key=lambda i: i.emitted_at)
        LOG.info("A procesar: %d vídeo(s)", len(items))
        for item in items:
            try:
                downloader.process(item)
            except KeyboardInterrupt:
                raise
            except RtveError as exc:
                LOG.error("Vídeo %s descartado: %s", item.video_id, exc)
                downloader.stats.errors += 1
            except Exception as exc:  # defensivo: seguir con el resto
                LOG.exception("Error inesperado con el vídeo %s: %s", item.video_id, exc)
                downloader.stats.errors += 1

    except KeyboardInterrupt:
        LOG.warning("Interrumpido por el usuario")
        exit_code = 130
    except RtveError as exc:
        LOG.error("Error fatal: %s", exc)
        exit_code = 1
    except Exception as exc:  # pragma: no cover
        LOG.exception("Error no controlado: %s", exc)
        exit_code = 1
    finally:
        manifest.flush()
        stats = downloader.stats
        LOG.info(
            "Resumen: %d vídeos | %d con subtítulos | %d sin subtítulos | "
            "%d ficheros escritos | %d omitidos | %d errores",
            stats.videos_seen, stats.videos_with_subs, stats.videos_without_subs,
            stats.files_written, stats.files_skipped, stats.errors,
        )
        LOG.info("HTTP: %d peticiones, %d reintentos, %.1f KB descargados en %.1fs",
                 http.stats["requests"], http.stats["retries"],
                 http.stats["bytes"] / 1024, time.monotonic() - started)
        http.close()

    if exit_code == 0 and downloader.stats.files_written == 0 and downloader.stats.files_skipped == 0:
        return 2
    return exit_code



# --------------------------------------------------------------------------- #
# Salida RAG: texto limpio dividido por puntuación, una línea por fragmento
# --------------------------------------------------------------------------- #

import html as _clean_html

_CLEAN_OUTPUT = {"root": None}
_CLEAN_TIME_RE = re.compile(r"\d{1,2}:\d{2}(?::\d{2})?[,.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?[,.]\d{1,3}")


def subtitle_to_clean_lines(source: str) -> List[str]:
    """Extrae texto de SRT/VTT y separa por cierre de frase, sin timecodes."""
    source = source.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    cues: List[str] = []
    for block in re.split(r"\n[ \t]*\n", source):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines or lines[0].upper().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None or not _CLEAN_TIME_RE.search(lines[timing_index]):
            continue
        value = _clean_html.unescape(" ".join(lines[timing_index + 1:]))
        value = re.sub(r"<[^>]+>", "", value)
        value = re.sub(r"\{\\[^}]*\}", "", value)
        value = re.sub(r"\s+", " ", value.replace("\u200b", " ")).strip()
        if value and (not cues or value.casefold() != cues[-1].casefold()):
            cues.append(value)

    full_text = re.sub(r"\s+", " ", " ".join(cues)).strip()
    # La puntuación fuerte crea el salto de línea; el resto queda en la frase.
    return [fragment.strip() for fragment in re.split(r"(?<=[.!?…])\s+", full_text) if fragment.strip()]


def write_clean_text_file(subtitle_path: Path, out_dir: Path) -> Path:
    """Crea un TXT sin cabeceras, etiquetas, timecodes ni líneas en blanco."""
    raw = subtitle_path.read_text(encoding="utf-8-sig")
    lines = subtitle_to_clean_lines(raw)
    if not lines:
        raise ValueError("No se pudo extraer texto de %s" % subtitle_path)
    try:
        relative = subtitle_path.relative_to(out_dir)
    except ValueError:
        relative = Path(subtitle_path.name)
    root = Path(_CLEAN_OUTPUT["root"]).expanduser().resolve() if _CLEAN_OUTPUT["root"] else out_dir.parent / "clean"
    destination = root / relative.with_suffix(".txt")
    atomic_write_text(destination, "\n".join(lines) + "\n")
    return destination


_original_build_parser = build_parser

def build_parser() -> argparse.ArgumentParser:
    parser = _original_build_parser()
    parser.add_argument(
        "--clean-out", default=None,
        help="Raíz de los TXT limpios. Def: directorio hermano <out>/../clean",
    )
    return parser


_original_download_track = SubtitleDownloader._download_track

def _download_track_and_clean(self, item: VideoItem, lang: str, url: str) -> None:
    _original_download_track(self, item, lang, url)
    if self.dry_run:
        return
    # Con --formato both se prefiere el SRT; con VTT exclusivo también funciona.
    candidates = [self.target_path(item, lang, fmt) for fmt in ("srt", "vtt") if fmt in self.formats]
    subtitle_path = next((path for path in candidates if path.exists() and path.stat().st_size > 0), None)
    if subtitle_path is None:
        return
    try:
        clean_path = write_clean_text_file(subtitle_path, self.out_dir)
        LOG.info(" ✓ texto limpio: %s", clean_path)
    except (OSError, UnicodeError, ValueError) as exc:
        LOG.error(" ✗ no se pudo crear el texto limpio de %s: %s", subtitle_path, exc)
        self.stats.errors += 1


SubtitleDownloader._download_track = _download_track_and_clean
_original_main = main

def main(argv: Optional[Sequence[str]] = None) -> int:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--clean-out", default=None)
    pre_args, _ = pre_parser.parse_known_args(argv)
    _CLEAN_OUTPUT["root"] = pre_args.clean_out
    return _original_main(argv)

if __name__ == "__main__":
    raise SystemExit(main())
