"""Sessies overleven een herstart — en het token staat nooit als token op schijf.

WAAROM DIT BESTAAT (2 sep 2026): sessies en het CSRF-token leefden in het procesgeheugen. Vijf
deploys op één werkdag herstartten de cockpit, en elke openstaande tab kreeg daarna 403 op zijn
POST. De drawer meldt dat inmiddels (#425), maar dat TOONT het probleem alleen. Dit neemt het weg.
"""
from __future__ import annotations

import json
import os
import stat
import time

from nooch_village import auth


def test_een_sessie_overleeft_een_nieuw_proces(tmp_path):
    """DE KERN. Twee losse SessionStore-instanties op hetzelfde pad staan model voor twee
    processen: de cockpit vóór en ná een deploy."""
    pad = str(tmp_path / "sessions.json")
    voor = auth.SessionStore(pad)
    token = voor.create("stefan@nooch.earth")

    na = auth.SessionStore(pad)                      # "herstart"
    assert na.get_username(token) == "stefan@nooch.earth"


def test_op_schijf_staat_geen_token_maar_een_hash(tmp_path):
    """Wie het bestand leest, mag er geen sessie mee kunnen kapen."""
    pad = str(tmp_path / "sessions.json")
    st = auth.SessionStore(pad)
    token = st.create("stefan@nooch.earth")

    rauw = (tmp_path / "sessions.json").read_text(encoding="utf-8")
    assert token not in rauw                         # het token zelf: nergens
    import hashlib
    assert hashlib.sha256(token.encode()).hexdigest() in rauw
    # de gebruikersnaam staat er wel — die is nodig om de sessie te kunnen gebruiken
    assert "stefan@nooch.earth" in rauw


def test_het_bestand_is_0600(tmp_path):
    """Komt uit atomic_write_json (mkstemp maakt 0600, os.replace behoudt de mode). Getest omdat
    'het gebeurt vanzelf' geen garantie is."""
    pad = str(tmp_path / "sessions.json")
    auth.SessionStore(pad).create("stefan@nooch.earth")
    modus = stat.S_IMODE(os.stat(pad).st_mode)
    assert modus == 0o600, oct(modus)


def test_een_verlopen_sessie_overleeft_de_herstart_NIET(tmp_path, monkeypatch):
    """Persistent maken mag geen sessies onsterfelijk maken. De vervaldatum is een absolute tijd
    (time.time), dus hij betekent in het volgende proces hetzelfde."""
    pad = str(tmp_path / "sessions.json")
    token = auth.SessionStore(pad, ttl=10).create("stefan@nooch.earth")
    later = time.time() + 11
    monkeypatch.setattr(auth.time, "time", lambda: later)
    assert auth.SessionStore(pad).get_username(token) is None


def test_verlopen_sessies_worden_opgeruimd_bij_het_laden(tmp_path, monkeypatch):
    """Anders groeit het bestand eeuwig met dode sessies."""
    pad = str(tmp_path / "sessions.json")
    st = auth.SessionStore(pad, ttl=10)
    st.create("a@nooch.earth")
    st.create("b@nooch.earth")
    assert len(json.loads((tmp_path / "sessions.json").read_text())) == 2

    later = time.time() + 11
    monkeypatch.setattr(auth.time, "time", lambda: later)
    auth.SessionStore(pad)                           # herstart ruimt op
    assert json.loads((tmp_path / "sessions.json").read_text()) == {}


def test_uitloggen_werkt_over_de_herstart_heen(tmp_path):
    pad = str(tmp_path / "sessions.json")
    st = auth.SessionStore(pad)
    token = st.create("stefan@nooch.earth")
    st.delete(token)
    assert auth.SessionStore(pad).get_username(token) is None


def test_invalidate_user_is_geen_no_op_meer(tmp_path):
    """Was een NO-OP zolang de store in het geheugen leefde. Nu de sessies een herstart overleven,
    MOET hij echt werken: anders overleeft een sessie ook een wachtwoordwijziging."""
    pad = str(tmp_path / "sessions.json")
    st = auth.SessionStore(pad)
    oud1, oud2 = st.create("stefan@nooch.earth"), st.create("stefan@nooch.earth")
    ander = st.create("nina@nooch.earth")
    nieuw = st.create("stefan@nooch.earth")

    assert st.invalidate_user("stefan@nooch.earth", keep_token=nieuw) == 2
    na = auth.SessionStore(pad)
    assert na.get_username(oud1) is None and na.get_username(oud2) is None
    assert na.get_username(nieuw) == "stefan@nooch.earth"     # de eigen, verse sessie blijft
    assert na.get_username(ander) == "nina@nooch.earth"       # een ander raak je niet


def test_een_onleesbaar_bestand_start_leeg_MAAR_LUID(tmp_path, caplog):
    """`read_json` gooit bewust op een corrupt bestand — stil leeg opstarten en dan overschrijven
    is hoe je data verliest. Die regel geldt voor RECORDS. Sessies zijn een CACHE: kwijt betekent
    opnieuw inloggen, en een cockpit die niet start is strikt erger.

    Leeg beginnen mag dus. Stil beginnen niet — dat is het verschil tussen fail-open en wegkijken."""
    import logging as _l
    pad = tmp_path / "sessions.json"
    pad.write_text("{dit is geen json", encoding="utf-8")
    with caplog.at_level(_l.WARNING):
        st = auth.SessionStore(str(pad))
    assert "onleesbaar" in caplog.text and "opnieuw in" in caplog.text
    token = st.create("stefan@nooch.earth")
    assert st.get_username(token) == "stefan@nooch.earth"


def test_zonder_pad_blijft_hij_in_het_geheugen(tmp_path):
    """Dezelfde code, lege schrijfroute — geen tweede implementatie."""
    st = auth.SessionStore()
    token = st.create("stefan@nooch.earth")
    assert st.get_username(token) == "stefan@nooch.earth"
    assert not list(tmp_path.iterdir())


# ── het CSRF-token, dat anders de halve fix zou zijn ──────────────────────────────────────────

def test_het_csrf_token_overleeft_ook(tmp_path):
    """Maak je alleen de SESSIE persistent, dan krijgt een tab die openstond tijdens een deploy nog
    steeds 403 — nu met 'CSRF token invalid' in plaats van 'Not logged in'. Voor de mens is dat
    hetzelfde: toevoegen werkt niet."""
    pad = str(tmp_path / "csrf.json")
    assert auth.load_or_create_csrf(pad) == auth.load_or_create_csrf(pad)


def test_het_csrf_bestand_is_0600(tmp_path):
    pad = str(tmp_path / "csrf.json")
    auth.load_or_create_csrf(pad)
    assert stat.S_IMODE(os.stat(pad).st_mode) == 0o600


def test_een_kapot_csrf_bestand_geeft_een_vers_token(tmp_path):
    """Fail-open naar het gedrag van vóór deze wijziging: een nieuw token per start. Nooit een
    cockpit die niet opkomt."""
    pad = tmp_path / "csrf.json"
    eerste = auth.load_or_create_csrf(str(pad))
    pad.write_text("{kapot", encoding="utf-8")
    tweede = auth.load_or_create_csrf(str(pad))
    assert tweede != eerste and len(tweede) >= 32
