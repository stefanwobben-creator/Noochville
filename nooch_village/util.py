"""Gedeelde hulpfuncties voor NoochVillage."""
from __future__ import annotations

import fcntl
import functools
import json
import logging
import os
import tempfile
import threading
import time

_log = logging.getLogger("nooch.util")


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


class _FileLock:
    """Proces-breed slot per bestandspad: een threading.RLock (intra-proces, reentrant, goedkoop) MÉT een
    fcntl.flock op een lockfile (<pad>.lock) eromheen voor de PROCESGRENS — cockpit én daemon schrijven
    dezelfde json (projects.json, attachments.json). De threading-lock guardt de reentrancy én de
    fd-boekhouding; de flock wordt alleen op de BUITENSTE acquire gepakt (fcntl is niet reentrant per proces).

    Crash-veilig: flock hangt aan de open file description; sterft een proces met het slot vast, dan sluit
    het OS de fd en geeft de flock automatisch vrij — geen deadlock. Timeout (NOOCH_FILE_LOCK_TIMEOUT_S,
    default 10s): nooit eeuwig blokkeren → na de timeout loggen + TimeoutError (nette fout i.p.v. hang).

    Reads nemen dit slot bewust NIET (de board-watch/read-paden blijven lock-vrij)."""

    def __init__(self, path: str):
        self.lockpath = os.path.abspath(path) + ".lock"
        self._rlock = threading.RLock()
        self._fd: int | None = None
        self._depth = 0

    def __enter__(self):
        self._rlock.acquire()                                 # intra-proces (reentrant)
        try:
            if self._depth == 0:                              # buitenste acquire → pak de flock
                os.makedirs(os.path.dirname(self.lockpath) or ".", exist_ok=True)
                fd = os.open(self.lockpath, os.O_CREAT | os.O_RDWR, 0o600)
                timeout = float(os.getenv("NOOCH_FILE_LOCK_TIMEOUT_S", "10"))
                deadline = time.monotonic() + timeout
                while True:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:                           # slot bij een ander proces → kort wachten
                        if time.monotonic() >= deadline:
                            os.close(fd)
                            _log.error("file_lock timeout (%.1fs) op %s — andere schrijver gaf niet op",
                                       timeout, self.lockpath)
                            raise TimeoutError(f"file_lock timeout ({timeout}s) op {self.lockpath}")
                        time.sleep(0.05)
                self._fd = fd
            self._depth += 1
        except BaseException:
            self._rlock.release()                             # geen half-acquire achterlaten
            raise
        return self

    def __exit__(self, *exc):
        self._depth -= 1
        if self._depth == 0 and self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None
        self._rlock.release()
        return False


_FILE_LOCKS: dict[str, _FileLock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def file_lock(path: str) -> _FileLock:
    """Proces-breed slot per bestandspad (threading + fcntl), zodat een read-modify-write of append
    serialiseert — óók over de procesgrens (cockpit ↔ daemon). Eén registry voor de hele app: modules die
    hetzelfde pad schrijven delen hetzelfde slot. Reads nemen dit slot bewust NIET (board-watch lock-vrij)."""
    key = os.path.abspath(path)
    with _FILE_LOCKS_GUARD:
        lk = _FILE_LOCKS.get(key)
        if lk is None:
            lk = _FILE_LOCKS[key] = _FileLock(path)
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


def synchronized(method):
    """Schrijfpad-wrapper (concurrency-safe): serialiseer via het gedeelde bestandsslot (file_lock, per
    pad) én lees VERS van schijf ONDER het slot (`self._load()`) vóór de mutatie. Zo muteert geen
    schrijver meer op een in-memory kopie van vóór het slot, en overleven gelijktijdige schrijvers
    elkaars mutaties (geen lost update). Reads blijven ongewrapt → lock-vrij.

    Eén plek voor ProjectLedger, AttachmentStore-stijl en WerkoverlegStore (reference, don't copy). De
    store moet `self.path` en een `self._load()` (verse read van schijf) hebben."""
    @functools.wraps(method)
    def _wrapped(self, *args, **kwargs):
        with file_lock(self.path):
            self._load()                        # verse toestand onder het slot
            return method(self, *args, **kwargs)
    return _wrapped


_REFUSE_LOG = logging.getLogger("nooch.refuse")


def refuse(code: str, reason: str, **ctx) -> bool:
    """Een bewuste weigering is een gebeurtenis, geen non-event: log een WARNING met een STABIELE
    `code` + reden + context, en retourneer False (het sentinel). Gedeeld fail-loud-primitief."""
    extra = " ".join(f"{k}={v!r}" for k, v in ctx.items())
    _REFUSE_LOG.warning("%s: %s%s", code, reason, (" | " + extra) if extra else "")
    return False


class JsonStore:
    """Concurrency-veilige basis voor een JSON-store. Bezit `self.path`, levert `_load()` (verse read
    van schijf) en `_save()` — de ENIGE `atomic_write_json`-route. Niemand schrijft zelf naar het
    bestand; wie dat wél doet valt buiten deze basis en wordt door de guard-test geweigerd.

    Subklassen declareren `_WRITE_METHODS` (hun schrijfmethoden); die worden bij class-creatie
    automatisch met `synchronized` gewrapt: `file_lock` + een verse `_load()` ONDER het slot vóór de
    mutatie, zodat gelijktijdige processen (cockpit ↔ daemon) elkaars schrijf niet overschrijven (geen
    lost update). Reads blijven ongewrapt (lock-vrij).

    Subklasse-contract (class-attributen):
      - `_STATE`   = naam van het in-memory state-attribuut (default '_items').
      - `_default` = factory voor de lege staat (default `dict`; zet `list` voor een lijst-store).
      - `_EXPECT`  = verwacht top-level type voor read_json (default `dict`; `list` bij een lijst-store).
      - `_WRITE_METHODS` = tuple met de namen van de schrijfmethoden die het slot moeten nemen.
    Een schrijfmethode muteert `self.<_STATE>` en roept `self._save()` aan (nooit `atomic_write_json` zelf)."""

    _WRITE_METHODS: tuple = ()
    _STATE: str = "_items"
    _default = dict          # factory (het type zelf → bindt niet aan de instance)
    _EXPECT: type = dict

    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        # Wrap ALLEEN de in déze subklasse gedeclareerde schrijfmethoden (geen dubbele wrap bij nesting).
        for name in cls.__dict__.get("_WRITE_METHODS", ()):
            meth = cls.__dict__.get(name)
            if callable(meth):
                setattr(cls, name, synchronized(meth))

    def __init__(self, path: str):
        self.path = path
        self._load()

    def _load(self) -> None:
        """Verse read van schijf → het state-attribuut. Aangeroepen door `synchronized` ONDER het slot."""
        setattr(self, self._STATE, read_json(self.path, self._default(), expect=self._EXPECT))

    def _save(self) -> None:
        """De enige schrijfroute. Alleen aan te roepen vanuit een @synchronized-schrijfmethode."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        atomic_write_json(self.path, getattr(self, self._STATE))
