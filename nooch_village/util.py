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
