"""Polite HTTP: browser headers, about 1 request/second per host, retries with backoff, on-disk cache."""
import hashlib
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .config import get_settings

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
BASE_HEADERS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

_last_hit: dict[str, float] = {}
_lock = threading.Lock()
_client: httpx.Client | None = None


def client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(headers=BASE_HEADERS, timeout=45, follow_redirects=True)
    return _client


def _throttle(url: str, min_gap: float):
    host = urlparse(url).netloc
    with _lock:
        now = time.time()
        slot = max(now, _last_hit.get(host, 0) + min_gap)
        _last_hit[host] = slot
    if slot > now:
        time.sleep(slot - now)


def _retryable(e: BaseException) -> bool:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        return code in (401, 403, 429) or code >= 500
    return isinstance(e, httpx.TransportError)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1.5, max=10),
       retry=retry_if_exception(_retryable), reraise=True)
def get(url: str, params: dict | None = None, headers: dict | None = None,
        min_gap: float = 1.0) -> httpx.Response:
    _throttle(url, min_gap)
    r = client().get(url, params=params, headers=headers or {})
    r.raise_for_status()
    return r


def cache_path(kind: str, key: str, ext: str) -> Path:
    d = get_settings().data_dir / kind
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{hashlib.sha1(key.encode()).hexdigest()[:20]}.{ext}"


def get_cached_text(url: str, max_age_h: float = 24, kind: str = "html", **kw) -> str:
    p = cache_path(kind, url, "html")
    if p.exists() and time.time() - p.stat().st_mtime < max_age_h * 3600:
        return p.read_text(encoding="utf-8")
    r = get(url, **kw)
    p.write_text(r.text, encoding="utf-8")
    return r.text


def get_cached_json(url: str, params: dict | None = None, max_age_h: float = 0.5,
                    kind: str = "json", **kw):
    key = url + json.dumps(params or {}, sort_keys=True)
    p = cache_path(kind, key, "json")
    if p.exists() and time.time() - p.stat().st_mtime < max_age_h * 3600:
        return json.loads(p.read_text(encoding="utf-8"))
    data = get(url, params=params, **kw).json()
    p.write_text(json.dumps(data), encoding="utf-8")
    return data
