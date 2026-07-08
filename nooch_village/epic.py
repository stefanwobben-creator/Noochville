"""EPIC-aardbol — NASA EPIC (natural) ophalen en de frames proxyen, zodat de NASA-key nooit in de
browser lekt.

Snel + licht (2026-07-08):
- We halen de kleine ~512px **thumbnail-JPEG's** op i.p.v. de volle 2048px-PNG die we tóch terugschaalden
  → veel kleinere download én geen server-side Pillow-resize meer nodig.
- We beperken tot `_N_FRAMES` posities (genoeg voor een vloeiende draaiing, minder downloads).
- We cachen op **SCHIJF** (`data/epic_cache/`), zodat een deploy/herstart geen koude her-download geeft
  (de in-memory cache was elke herstart weg). Frame-bytes zijn immutable → geen TTL nodig; metadata 1u.

Fail-closed: geen `NASA_API_KEY` of een API-/parse-/format-fout → None. De UI valt terug op een nette
melding; nooit een kapotte pagina.
"""
from __future__ import annotations
import json
import os
import re
import time

import requests

_META_URL = "https://api.nasa.gov/EPIC/api/natural"
# De KLEINE thumbnail (~512px JPEG) i.p.v. de volle 2048px-PNG. De ronde CSS-container (object-fit:cover)
# verzorgt de weergave, dus terugschalen is overbodig.
_THUMB_URL = "https://api.nasa.gov/EPIC/archive/natural/{y}/{m}/{d}/thumbs/{image}.jpg"
_TTL = 3600.0            # metadata: 1 uur
_N_FRAMES = 8            # posities voor de draaiing — genoeg voor een vloeiende spin, licht qua downloads
_FRAME_MAX_AGE = 14 * 86400   # oude frame-bestanden opruimen (schijf-groei begrenzen)

# Schijf-cache: overleeft deploys/herstarts. Onder data/ (gitignored). Override via EPIC_CACHE_DIR.
_CACHE_DIR = os.getenv("EPIC_CACHE_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "epic_cache")
_META_FILE = os.path.join(_CACHE_DIR, "meta.json")
_FRAME_DIR = os.path.join(_CACHE_DIR, "frames")

_meta_cache: dict = {"ts": 0.0, "data": None}
_frame_mem: dict[str, bytes] = {}

_IMAGE_RE = re.compile(r"[A-Za-z0-9_]+")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _key() -> str:
    return os.getenv("NASA_API_KEY", "").strip()


def _ensure_dirs() -> None:
    try:
        os.makedirs(_FRAME_DIR, exist_ok=True)
    except OSError:
        pass


def _prune_frames() -> None:
    """Best-effort: verwijder frame-bestanden ouder dan _FRAME_MAX_AGE (begrenst de schijf-groei)."""
    try:
        now = time.time()
        for fn in os.listdir(_FRAME_DIR):
            fp = os.path.join(_FRAME_DIR, fn)
            if os.path.isfile(fp) and now - os.path.getmtime(fp) > _FRAME_MAX_AGE:
                os.remove(fp)
    except OSError:
        pass


def latest_frames() -> list[dict] | None:
    """De EPIC-frames van de laatste dag als [{image, date (YYYY-MM-DD), caption (UTC-tijd)}],
    chronologisch, teruggesampled naar max _N_FRAMES. None bij ontbrekende key of een fout. 1u gecachet
    (in-memory + schijf, zodat een herstart geen koude NASA-call forceert)."""
    now = time.time()
    if _meta_cache["data"] is not None and now - _meta_cache["ts"] < _TTL:
        return _meta_cache["data"]
    try:                                          # schijf-cache overleeft herstart
        if os.path.exists(_META_FILE) and now - os.path.getmtime(_META_FILE) < _TTL:
            with open(_META_FILE, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list) and data:
                _meta_cache.update(ts=now, data=data)
                return data
    except (OSError, ValueError):
        pass
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
    valid = [it for it in raw if it.get("image") and it.get("date")]
    if not valid:
        return None
    if len(valid) <= _N_FRAMES:
        picks = valid
    else:                                          # evenwichtig terugsamplen naar _N_FRAMES posities
        n = _N_FRAMES
        picks = [valid[(i * (len(valid) - 1)) // (n - 1)] for i in range(n)]
    frames = [{"image": it["image"], "date": it["date"][:10], "caption": it["date"]} for it in picks]
    _meta_cache.update(ts=now, data=frames)
    _ensure_dirs()
    try:
        with open(_META_FILE, "w", encoding="utf-8") as fh:
            json.dump(frames, fh)
    except OSError:
        pass
    _prune_frames()
    return frames


def frame_bytes(image: str, date: str) -> bytes | None:
    """De ~512px thumbnail-JPEG van één frame. None bij ontbrekende key, een API-fout, geen geldige JPEG,
    of een onveilige image-id/datum (voorkomt SSRF/path-traversal in de proxy-url). Gecachet op schijf →
    overleeft een deploy/herstart (frame-bytes zijn immutable)."""
    if not image or not date or not _IMAGE_RE.fullmatch(image) or not _DATE_RE.fullmatch(date):
        return None
    if image in _frame_mem:
        return _frame_mem[image]
    path = os.path.join(_FRAME_DIR, f"{image}.jpg")
    try:                                          # schijf-cache: immutable → direct serveren
        if os.path.exists(path):
            with open(path, "rb") as fh:
                data = fh.read()
            if data:
                _frame_mem[image] = data
                return data
    except OSError:
        pass
    key = _key()
    if not key:
        return None
    y, m, d = date.split("-")
    url = _THUMB_URL.format(y=y, m=m, d=d, image=image)
    try:
        r = requests.get(url, params={"api_key": key}, timeout=15)
        r.raise_for_status()
        data = r.content
    except requests.RequestException:
        return None
    if not data or not data.startswith(b"\xff\xd8\xff"):   # geen geldige JPEG → fail-closed, geen crash
        return None
    _frame_mem[image] = data
    _ensure_dirs()
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError:
        pass
    return data
