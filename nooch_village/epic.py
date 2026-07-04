"""EPIC-aardbol — NASA EPIC (natural) ophalen en de frames proxyen, zodat de NASA-key nooit in de
browser lekt. Zowel de metadata (laatste set frames) als de PNG-thumbs worden 1 uur in-memory
gecachet, zodat niet elke paginaload NASA aanroept.

Fail-closed: geen `NASA_API_KEY` of een API-/parse-fout → None. De UI valt dan terug op een nette
melding; nooit een kapotte pagina.
"""
from __future__ import annotations
import io
import os
import re
import time

import requests

_META_URL = "https://api.nasa.gov/EPIC/api/natural"
# De VOLLE 2048px-PNG; we resizen 'm server-side met Pillow naar ~512px (kolombreed genoeg, licht).
_PNG_URL = "https://api.nasa.gov/EPIC/archive/natural/{y}/{m}/{d}/png/{image}.png"
_TTL = 3600.0            # 1 uur
_N_FRAMES = 8            # ~8 frames, gesampled over de hele dag → volle rotatie (ook Europa)
_SIZE = 512             # doelformaat (px) na resize

_meta_cache: dict = {"ts": 0.0, "data": None}
_png_cache: dict[str, tuple[float, bytes]] = {}

_IMAGE_RE = re.compile(r"[A-Za-z0-9_]+")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _key() -> str:
    return os.getenv("NASA_API_KEY", "").strip()


def latest_frames() -> list[dict] | None:
    """De laatste ~6 EPIC-frames als [{image, date (YYYY-MM-DD), caption (UTC-tijd)}], chronologisch.
    None bij ontbrekende key of een fout. 1 uur gecachet."""
    now = time.time()
    if _meta_cache["data"] is not None and now - _meta_cache["ts"] < _TTL:
        return _meta_cache["data"]
    key = _key()
    if not key:
        return None
    try:
        r = requests.get(_META_URL, params={"api_key": key}, timeout=8)
        r.raise_for_status()
        raw = r.json()
    except (requests.RequestException, ValueError):
        return None
    if not isinstance(raw, list) or not raw:
        return None
    # Verdeel de frames evenwichtig over de HELE dag i.p.v. alleen het laatste stukje, zodat de aarde
    # een volle rotatie draait en ook Europa/Afrika langskomt (niet enkel de Pacific).
    valid = [it for it in raw if it.get("image") and it.get("date")]
    if not valid:
        return None
    n = min(_N_FRAMES, len(valid))
    picks = ([valid[(i * (len(valid) - 1)) // (n - 1)] for i in range(n)] if n > 1 else valid[:1])
    frames = [{"image": it["image"], "date": it["date"][:10], "caption": it["date"]} for it in picks]
    _meta_cache["ts"] = now
    _meta_cache["data"] = frames
    return frames


def _resize_png(src: bytes) -> bytes | None:
    """Volle EPIC-PNG (2048px) → ~512px PNG via Pillow. None bij een Pillow-fout (fail-closed)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(src)).convert("RGB")
        im.thumbnail((_SIZE, _SIZE))
        out = io.BytesIO()
        im.save(out, format="PNG", optimize=True)
        return out.getvalue()
    except Exception:      # noqa: BLE001 — elke Pillow-/decode-fout → nette fallback, geen crash
        return None


def frame_bytes(image: str, date: str) -> bytes | None:
    """De naar ~512px geresizede PNG van één frame (1 uur gecachet). None bij ontbrekende key, een
    API-/Pillow-fout, of een onveilige image-id/datum (voorkomt SSRF/path-traversal in de proxy-url)."""
    if not image or not date or not _IMAGE_RE.fullmatch(image) or not _DATE_RE.fullmatch(date):
        return None
    hit = _png_cache.get(image)
    now = time.time()
    if hit and now - hit[0] < _TTL:
        return hit[1]
    key = _key()
    if not key:
        return None
    y, m, d = date.split("-")
    url = _PNG_URL.format(y=y, m=m, d=d, image=image)
    try:
        r = requests.get(url, params={"api_key": key}, timeout=15)
        r.raise_for_status()
        src = r.content
    except requests.RequestException:
        return None
    if not src:
        return None
    data = _resize_png(src)
    if not data:
        return None
    _png_cache[image] = (now, data)
    return data
