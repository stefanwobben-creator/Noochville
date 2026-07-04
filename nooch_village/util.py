"""Gedeelde hulpfuncties voor NoochVillage."""
from __future__ import annotations

import json
import os
import tempfile
import threading


def is_due(last_ts: float, now: float, interval_s: float) -> bool:
    """Is een periodieke taak weer aan de beurt?

    interval_s <= 0 → altijd (geen cadans). Anders pas weer als er minstens
    interval_s seconden verstreken zijn sinds last_ts.
    """
    if interval_s <= 0:
        return True
    return (now - last_ts) >= interval_s


def run_bounded(fn, timeout_s: float):
    """Voer fn() uit met een harde tijdslimiet via een daemon-thread.

    Geeft (True, resultaat) als fn binnen de tijd klaar is, (False, exception) als fn
    een uitzondering gooide, en (False, None) bij time-out. Bij time-out blijft de
    thread (daemon) nog draaien tot fn zelf klaar is, maar de aanroeper wacht niet —
    zo kan een trage, flaky call (zoals Google Trends-backoff) het kritieke pad niet
    gijzelen.
    """
    box: dict = {}

    def worker():
        try:
            box["value"] = fn()
        except Exception as exc:               # noqa: BLE001 — bewust alles vangen
            box["error"] = exc

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        return (False, None)                    # time-out
    if "error" in box:
        return (False, box["error"])
    return (True, box.get("value"))


def read_json(path: str, default, expect=dict):
    """Lees JSON van `path`.

    - Bestaat het bestand niet → `default` (normale eerste run).
    - Bestaat het wél maar is het onleesbaar (OSError/PermissionError) of corrupt
      (JSONDecodeError), of is het top-level type niet `expect` → **RAISE**.

    Zo wordt "kan het bestand niet lezen" nooit stil "leeg": een permissie-fout of
    corrupt bestand knalt luid i.p.v. dat een store leeg opstart (en bij de volgende
    save het bestand overschrijft). Zet `expect=None` om de type-check over te slaan.
    """
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Kan {path} niet lezen/parsen: {e}") from e
    if expect is not None and not isinstance(d, expect):
        raise RuntimeError(f"{path}: verwacht {expect.__name__}, kreeg {type(d).__name__}")
    return d


_FILE_LOCKS: dict[str, threading.RLock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def file_lock(path: str) -> threading.RLock:
    """Proces-breed slot per bestandspad, zodat een read-modify-write óf een append op hetzelfde
    bestand serialiseert. Eén registry voor de hele app: twee modules die hetzelfde pad schrijven
    (bv. de AttachmentStore én de artefact-changelog) delen zo hetzelfde slot. Een threading-slot
    volstaat — één cockpit-proces schrijft; multi-proces vergrendeling (fcntl) is hier niet nodig."""
    key = os.path.abspath(path)
    with _FILE_LOCKS_GUARD:
        lk = _FILE_LOCKS.get(key)
        if lk is None:
            lk = _FILE_LOCKS[key] = threading.RLock()
        return lk


def atomic_write_json(path: str, obj) -> None:
    """Schrijf obj als JSON naar path via een tijdelijk bestand in dezelfde map.

    Gebruikt os.replace() zodat een onderbreking (Ctrl-C, crash) het oude
    bestand intact laat — nooit een half geschreven toestandsbestand.
    """
    dir_ = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
