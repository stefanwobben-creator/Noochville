"""De voorraad, niet alleen de instroom.

De laatste meter vuurt op het MOMENT van parkeren. Wat daarvóór al vastliep blijft liggen: die items
dragen `routed=True`, en dat is precies de garantie die voorkomt dat de router elke puls opnieuw
dezelfde LLM-call doet. Zelfde les als de notificatie-opruiming van 14 aug 2026: **code repareren
haalt de emissies van die code niet weg** — en hier andersom: het haalt de STILSTAND niet weg.
"""
from __future__ import annotations

import pytest

from nooch_village import cockpit2, escalation_router as er, vastgelopen_route as vr
from nooch_village.human_inbox import FOUNDER_ROLE_ID

#: de mens die de founder-rol vervult in deze fixtures — het ADRES sinds de vervuller-pass, en
#: sinds 20 september 2026 het ENIGE adres: alles wat vastloopt komt eerst bij de founder.
#: De fixture maakt hem als echt persoon-record aan; deze naam is waar de tests op matchen.
FOUNDER_NAAM = "Stefan Wobben"

MENS = "vastgelopen op 1 item(s) — wacht op een mens of externe partij"
ROLWERK = "vastgelopen op 1 item(s) — payload onvolledig na herstelpoging: veld term"


@pytest.fixture
def dd(tmp_path, monkeypatch):
    cockpit2._bootstrap(str(tmp_path))
    # `mens_vervullers` en niet meer `door_mens_bemand`: `route_werk` kijkt sinds de vervuller-pass
    # naar WIE een rol draagt, niet naar of hij gedragen wordt. De founder-rol krijgt hier één
    # vervuller, dus het werk landt bij die mens met de rol als context.
    # Patch op `signaal.mensen_van` en niet meer op `cockpit2.mens_vervullers`: die laatste
    # delegeert er sinds B2 naartoe, en de signaal-routering (die het bericht bezorgt) leest
    # dezelfde functie. Eén plek patchen dekt nu allebei — dat was precies het doel van die
    # samenvoeging.
    # DE PERSOON BESTAAT ECHT in deze fixture, en dat is sinds 20 september 2026 nodig: de
    # bestemming is geen ROL meer maar de founder als MENS (`signaal.terugval`), en het rapport
    # zoekt zijn naam op in `people`. Een los persoon-id zonder record leverde "p-founder" in de
    # verdeling op — precies het onleesbare id dat de test hieronder verbiedt.
    from nooch_village import signaal as _sig
    st0 = cockpit2._Stores(str(tmp_path))
    persoon = st0.people.add("Stefan Wobben", "stefan@nooch.earth")
    monkeypatch.setattr(_sig, "mensen_van",
                        lambda _st, rol: [persoon.id]
                        if rol in (FOUNDER_ROLE_ID, _sig.TERUGVAL_ROL) else [])
    monkeypatch.setattr(er, "_vraag_llm", lambda *a, **k: None)      # geen model → founder
    return str(tmp_path)


def _founder_id(dd):
    """Het persoon-id van de founder in deze fixture. Opgevraagd via `signaal.terugval` en niet als
    constante: de fixture maakt het record aan, en dit is dezelfde weg die de code zelf loopt."""
    from nooch_village import signaal as _sig
    return _sig.terugval(cockpit2._Stores(dd))


def _dm_aan(st, persoon_id):
    """De DM-teksten die deze persoon kreeg. Het SPOOR van een melding is sinds B2 een bericht in
    een kanaal in plaats van een rij in een wachtrij; de redenering eromheen is ongewijzigd."""
    return [e.get("text") or "" for k in st.channels.kanalen_van(persoon_id)
            for e in st.channels.trail(k)]

def _vastgelopen(dd, *, reden=MENS, stap="Laat de samples testen in een erkend lab") -> str:
    st = cockpit2._Stores(dd)
    pid = st.projects.create("harry_hemp", "PHA-aanbodlandschap", "human")
    cl = st.projects.checklist_add(pid, title="Uitvoerplan")
    st.projects.check_add(pid, cl["id"], stap)
    st.projects.block(pid, reden)
    return pid


# ── Guard 1: alleen een mens-park-reden ─────────────────────────────────────

def test_alleen_mens_werk_gaat_naar_een_mens(dd):
    _vastgelopen(dd, reden=ROLWERK)
    v = vr.pas(dd, apply=True)
    assert v["in_aanmerking"] == 0 and v["geland"] == []


def test_een_mens_park_reden_landt_wel(dd):
    pid = _vastgelopen(dd)
    v = vr.pas(dd, apply=True)
    assert v["in_aanmerking"] == 1 and len(v["geland"]) == 1
    assert v["geland"][0]["pid"] == pid
    n = _dm_aan(cockpit2._Stores(dd), _founder_id(dd))
    assert n and "erkend lab" in n[-1]


# ── Guard 2: alleen wat nu nog open is ──────────────────────────────────────

def test_een_afgevinkte_stap_is_geen_vraag_meer(dd):
    pid = _vastgelopen(dd)
    st = cockpit2._Stores(dd)
    p = st.projects.get(pid)
    cl = p["checklists"][0]
    st.projects.check_toggle(pid, cl["id"], cl["items"][0]["id"])
    assert vr.pas(dd, apply=True)["stappen"] == 0


# ── Guard 3: idempotent op het spoor ────────────────────────────────────────

def test_twee_keer_draaien_levert_geen_tweede_melding(dd):
    _vastgelopen(dd)
    eerste = vr.pas(dd, apply=True)
    tweede = vr.pas(dd, apply=True)
    assert len(eerste["geland"]) == 1
    assert tweede["geland"] == [] and tweede["al_gemeld"] == 1
    n = _dm_aan(cockpit2._Stores(dd), _founder_id(dd))
    assert len(n) == 1, "dezelfde vraag twee keer verstuurd"


def test_de_idempotentie_hangt_aan_de_MELDING_niet_aan_een_vlag():
    """Een vlag op het item en een verstuurde melding zijn twee plekken voor één feit; die drijven
    uiteen zodra iemand de inbox opruimt. Zelfde regel als `reference, don't copy`."""
    import inspect
    bron = inspect.getsource(vr.al_geland)
    assert "st.channels" in bron          # het spoor is de verstuurde DM, geen losse vlag


# ── De droge loop is de default ─────────────────────────────────────────────

def test_droge_loop_schrijft_niets(dd):
    _vastgelopen(dd)
    v = vr.pas(dd)                                     # geen apply
    assert len(v["geland"]) == 1 and v["toegepast"] is False
    assert not _dm_aan(cockpit2._Stores(dd), _founder_id(dd))


def test_filteren_op_één_rol(dd):
    _vastgelopen(dd)
    assert vr.pas(dd)["in_aanmerking"] == 1
    assert vr.pas(dd, owner="iemand_anders")["in_aanmerking"] == 0


# ── De droge loop moet de ENIGE beslissing meten die ertoe doet ──────────────

def _dm_kanalen(dd):
    """De DM-kanalen in het dorp. Sinds B2 (20 september 2026) landt een melding aan een mens hier
    en niet in een NotifStore; een kanaal-id draagt de twee persoon-ids die erin zitten."""
    from nooch_village import channels, signaal
    st = signaal._MiniStores(dd)
    return [k for k in st.channels.bestaande() if channels.soort_van(k) == channels.DM]


def _trail(dd, kanaal):
    from nooch_village import signaal
    return signaal._MiniStores(dd).channels.trail(kanaal)


def test_de_droge_loop_toont_waar_het_zou_landen(dd):
    """Een droge loop die alleen TELT laat de vraag onbeantwoord die het besluit draagt: routeren we,
    of dumpen we 33 items op één inbox? Dat zijn twee verschillende handelingen."""
    _vastgelopen(dd)
    v = vr.pas(dd)
    assert v["toegepast"] is False
    assert sum(v["verdeling"].values()) == 1
    assert list(v["gronden"]) == ["alles wat vastloopt komt eerst bij jou"]
    # en nog steeds niets geschreven — de founder kreeg geen DM
    assert not [e for k in _dm_kanalen(dd) if _founder_id(dd) in k
                for e in _trail(dd, k)]


def test_de_verdeling_noemt_de_rol_bij_naam_niet_bij_id(dd):
    """Een id in een verdeling is niet te lezen; de vraag is welke MENS dit krijgt."""
    _vastgelopen(dd)
    assert FOUNDER_NAAM in " ".join(vr.pas(dd)["verdeling"])


def test_het_rapport_toont_de_suggestie_per_toewijzing(dd, capsys):
    """DE ENIGE PLEK WAAR EEN TOEWIJZING NOG HERBEOORDEELBAAR IS (20 september 2026).

    De regel "op welke grond" onderaan het rapport is sinds `_mens_ontvanger` altijd de founder
    teruggeeft een CONSTANTE: "alles wat vastloopt komt eerst bij jou", voor elk geval hetzelfde.
    Niet verkeerd, maar zonder onderscheid — je kunt er geen enkele toewijzing mee wegen.

    De modelsuggestie is wél per geval verschillend, zat al in elk item van het verslag, en werd
    nergens geprint. Nu wel. Het blijft een VOORSTEL: de ontvanger is al bepaald en verandert hier
    niet door."""
    _vastgelopen(dd)
    vr.rapport(dd, apply=False)
    uit = capsys.readouterr().out
    assert "alles wat vastloopt komt eerst bij jou" in uit          # de constante grond blijft
    # De suggestie hangt aan een modelantwoord; zonder sleutel is hij leeg en hoort er niets te
    # staan — een lege "↳"-regel zou suggereren dat er een voorstel was.
    v = vr.pas(dd)
    heeft = [g for g in v["geland"] if g.get("suggestie")]
    assert ("↳" in uit) == bool(heeft), "een ↳-regel hoort te bestaan als en alleen als er een voorstel is"


def test_de_suggestie_verandert_de_bestemming_niet(dd):
    """DE GRENS. Het model mag iets vinden; het adres blijft de founder. Zou de suggestie de
    bestemming raken, dan is het geen voorstel meer maar een toewijzing door een model."""
    _vastgelopen(dd)
    v = vr.pas(dd, reason_fn=lambda *a, **k: '{"rol": "mother_earth__nooch__creator_of_shoes", '
                                            '"kind": "rol", "waarom": "materiaalvraag"}')
    assert list(v["gronden"]) == ["alles wat vastloopt komt eerst bij jou"]
    assert FOUNDER_NAAM in " ".join(v["verdeling"])
