"""EPIC-aardbol — NASA EPIC (natural) ophalen en de frames proxyen, zodat de NASA-key nooit in de
browser lekt.

Beeldkwaliteit als vanouds: de VOLLE 2048px-PNG wordt server-side met Pillow naar ~512px JPEG geschaald
(scherper dan NASA's eigen thumbnail), met alle frames van de dag voor een vloeiende draaiing. Wél behouden:
de **schijf-cache** (`data/epic_cache/`), zodat een deploy/herstart geen koude her-download geeft. De UI
toont bovendien een "Mother Earth is loading…"-indicator zolang het beeld nog binnenkomt.

Fail-closed: geen `NASA_API_KEY` of een API-/Pillow-fout → None. De UI valt terug op een nette melding.
"""
from __future__ import annotations
import io
import json
import os
import re
import time

import requests

_META_URL = "https://api.nasa.gov/EPIC/api/natural"
# De VOLLE 2048px-PNG; we resizen 'm server-side met Pillow naar ~512px JPEG (scherp + licht).
_PNG_URL = "https://api.nasa.gov/EPIC/archive/natural/{y}/{m}/{d}/png/{image}.png"
_TTL = 3600.0            # metadata: 1 uur
_N_FRAMES = 24           # max; een EPIC-dag heeft er ~13–22 → allemaal gebruiken voor kleine stapjes
_SIZE = 512             # doelformaat (px) na resize
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


def _resize_frame(src: bytes) -> bytes | None:
    """Volle EPIC-PNG (2048px) → ~512px JPEG via Pillow. JPEG i.p.v. PNG houdt de frames licht
    (~50 KB i.p.v. ~270 KB). None bij een Pillow-/decode-fout (fail-closed)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(src)).convert("RGB")
        im.thumbnail((_SIZE, _SIZE))
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=82, optimize=True)
        return out.getvalue()
    except Exception:      # noqa: BLE001 — elke Pillow-/decode-fout → nette fallback, geen crash
        return None


def frame_bytes(image: str, date: str) -> bytes | None:
    """De naar ~512px geresizede JPEG van één frame. None bij ontbrekende key, een API-/Pillow-fout, of een
    onveilige image-id/datum (voorkomt SSRF/path-traversal in de proxy-url). Gecachet op schijf → overleeft
    een deploy/herstart (frame-bytes zijn immutable)."""
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
    url = _PNG_URL.format(y=y, m=m, d=d, image=image)
    try:
        r = requests.get(url, params={"api_key": key}, timeout=15)
        r.raise_for_status()
        src = r.content
    except requests.RequestException:
        return None
    if not src:
        return None
    data = _resize_frame(src)                     # 2048px PNG → scherpe 512px JPEG
    if not data:
        return None
    _frame_mem[image] = data
    _ensure_dirs()
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError:
        pass
    return data
