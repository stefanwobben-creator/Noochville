"""Fase 8: de gespreklaag (project, cirkel, persoon) en wat er NIET mee vervangen wordt.

De brief vroeg "vervang de wall en @-notificaties door de channel-laag". Dat klopt voor de
@-vermelding, maar niet voor de NotifStore als geheel: van de 371 notificaties op productie
dragen er 24 een `entry_id` (= een wall-vermelding) en zijn er 338 aan een ROL gericht — werk dat
afgehandeld moet worden, geen gesprek. Die blijven de wachtrij op /inbox.

Deze tests bevriezen precies dat onderscheid, plus de dingen die er bij een volgende beurt zo weer
insluipen: een DM die twee kanalen wordt, een bericht zonder auteur, en een privégesprek dat in de
zoekresultaten opduikt.
"""
from __future__ import annotations

from nooch_village import channels, cockpit2

OWNER = "mother_earth__nooch__creator_of_shoes"
CIRKEL = "mother_earth__nooch"


def _stores(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _mens(st, naam, mail):
    """Een mens MET e-mail. `people.add` dedupliceert op naam, en `_bootstrap` zet al een paar
    mensen zonder e-mail neer — een bestaande naam hergebruiken geeft dus een persoon die niet
    op zijn mail te vinden is, en dan valt de vermelding terug op de notificatie. Daarom eigen
    namen, en de e-mail erbij gezet als de persoon al bestond."""
    p = st.people.add(naam, mail)
    if not getattr(p, "email", ""):
        st.people.set_email(p.id, mail) if hasattr(st.people, "set_email") else None
        p = st.people.by_email(mail) or p
    return p


# ── 1. de store ──────────────────────────────────────────────────────────────
def test_een_dm_is_richting_onafhankelijk():
    """A→B en B→A moeten hetzelfde kanaal zijn, anders krijg je twee halve gesprekken en mist
    iedereen de helft."""
    assert channels.dm_kanaal("b", "a") == channels.dm_kanaal("a", "b")
    assert channels.dm_leden(channels.dm_kanaal("b", "a")) == ["a", "b"]


def _dm_teksten(st):
    """Alle DM-berichtteksten. Sinds de inbox-migratie (20 sept 2026) landt een signalering als DM
    bij een mens in plaats van als item in een wachtrij."""
    from nooch_village import channels
    uit = []
    for k in st.channels.bestaande():
        if channels.soort_van(k) == channels.DM:
            uit += [e.get("text") or "" for e in st.channels.trail(k)]
    return uit

def test_een_project_kanaal_is_de_bestaande_wall(tmp_path):
    """Geen migratie: het project-kanaal leest en schrijft `project["log"]` via de ledger. Zou het
    een eigen kopie zijn, dan lopen 442 bestaande gesprekken en zeven lezers uit de pas."""
    dd, st = _stores(tmp_path)
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    st.channels.post(channels.project_kanaal(pid), "Via het kanaal", author_id="p1")
    assert [e["text"] for e in st.projects.get(pid)["log"]] == ["Via het kanaal"]
    assert [e["text"] for e in st.channels.trail(channels.project_kanaal(pid))] == ["Via het kanaal"]


def test_een_leeg_bericht_landt_niet(tmp_path):
    dd, st = _stores(tmp_path)
    assert st.channels.post(channels.circle_kanaal(CIRKEL), "   ", author_id="p1") is None
    assert st.channels.trail(channels.circle_kanaal(CIRKEL)) == []


def test_kanalen_van_een_mens_zijn_alleen_de_zijne(tmp_path):
    dd, st = _stores(tmp_path)
    st.channels.post(channels.dm_kanaal("a", "b"), "hoi", author_id="a")
    st.channels.post(channels.dm_kanaal("c", "d"), "hoi", author_id="c")
    assert st.channels.kanalen_van("a") == [channels.dm_kanaal("a", "b")]


# ── 2. de @-vermelding wordt een bericht ─────────────────────────────────────
def _wall(st, dd, pid, tekst, mail):
    return cockpit2.dispatch(dd, "proj_feed",
                             {"pid": [pid], "text": [tekst], "author": ["human:"], "next": ["/"]},
                             username=mail)


def test_een_vermelding_van_een_mens_landt_in_zijn_dm(tmp_path):
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    jij = _mens(st, "Testpersoon Twee", "twee@test.nl")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    _wall(st, dd, pid, "@Testpersoon Twee kijk jij hier even naar?", "een@test.nl")

    st2 = cockpit2._Stores(dd)
    trail = st2.channels.trail(channels.dm_kanaal(ik.id, jij.id))
    assert len(trail) == 1 and "kijk jij" in trail[0]["text"]
    # De herkomst reist mee: zonder het project erbij is het bericht niet terug te vinden.
    assert trail[0]["herkomst"]["project"] == pid


def test_de_vermelding_landt_precies_een_keer(tmp_path):
    """Precies het dubbele dat fase 8 opheft: één vermelding, één plek.

    De test heette `..._wordt_geen_notificatie_meer` en telde dat de NotifStore níét meegroeide.
    Die store bestaat sinds 20 september 2026 niet meer, dus die helft bewijst zichzelf. Wat blijft
    is de andere helft, en dat was altijd de echte eis: één vermelding levert ÉÉN bericht op."""
    dd, st = _stores(tmp_path)
    _mens(st, "Testpersoon Een", "een@test.nl")
    _mens(st, "Testpersoon Twee", "twee@test.nl")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    voor_dm = len(_dm_teksten(cockpit2._Stores(dd)))
    _wall(st, dd, pid, "@Testpersoon Twee even kijken?", "een@test.nl")
    assert len(_dm_teksten(cockpit2._Stores(dd))) == voor_dm + 1


def test_een_rol_met_vervuller_bereikt_die_mens(tmp_path):
    """`@rolnaam` gaat naar de MENS die de rol vervult, in zijn eigen DM met de afzender. Een rol
    heeft geen inbox; een mens wel."""
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    rec = st.records.get(OWNER)
    vervuller = next(f.id for f in st.assign.fillers_of(OWNER) if f.type == "person")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    _wall(st, dd, pid, f"@{cockpit2._name(rec)} pak jij dit op?", "een@test.nl")
    trail = cockpit2._Stores(dd).channels.trail(channels.dm_kanaal(ik.id, vervuller))
    assert len(trail) == 1 and "pak jij dit op" in trail[0]["text"]


def test_een_rol_zonder_mens_valt_terug_op_een_mens(tmp_path):
    """Deze test heette `..._valt_terug_op_de_wachtrij`. De wachtrij bestaat niet meer; de terugval
    is sinds 20 september 2026 een DM bij de founder.

    Het punt is onveranderd en het is waarom de test bestaat: werk bij niemand neerleggen is
    stiller en erger dan een melding te veel. `mother_earth` is de anchor-cirkel en heeft geen
    mens-vervuller, dus hier moet de terugval aantoonbaar werken."""
    dd, st = _stores(tmp_path)
    _mens(st, "Testpersoon Een", "een@test.nl")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    naam = cockpit2._name(st.records.get("mother_earth"))
    voor_dm = len(_dm_teksten(cockpit2._Stores(dd)))
    _wall(st, dd, pid, f"@{naam} pak jij dit op?", "een@test.nl")
    st2 = cockpit2._Stores(dd)
    assert len(_dm_teksten(st2)) == voor_dm + 1
    # En hij landt bij een MENS, niet in een kanaal dat niemand leest.
    from nooch_village import signaal
    founder = signaal.terugval(st2)
    assert founder and any(founder in channels.dm_leden(k) for k in st2.channels.bestaande()
                           if channels.soort_van(k) == channels.DM)


def test_jezelf_vermelden_maakt_geen_gesprek_met_jezelf(tmp_path):
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    _wall(st, dd, pid, "@Testpersoon Een nota bene", "een@test.nl")
    assert cockpit2._Stores(dd).channels.kanalen_van(ik.id) == []


# ── 3. het scherm ────────────────────────────────────────────────────────────
def test_messages_toont_de_drie_soorten(tmp_path):
    from nooch_village.views.messages import render_messages
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    jij = _mens(st, "Testpersoon Twee", "twee@test.nl")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    st.channels.post(channels.project_kanaal(pid), "projectpraat", author_id=ik.id)
    st.channels.post(channels.dm_kanaal(ik.id, jij.id), "hoi", author_id=ik.id)
    html = render_messages(st, ik=ik.id, csrf_token="t")
    for stuk in ("Projects", "Circles", "Direct", "Batch 4", "Testpersoon Twee"):
        assert stuk in html, stuk


def test_een_dm_heet_naar_de_ander(tmp_path):
    """Je opent een gesprek met iemand, niet een gesprek tussen twee mensen van wie jij er een bent."""
    from nooch_village.views.messages import _label
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    jij = _mens(st, "Testpersoon Twee", "twee@test.nl")
    assert _label(st, channels.dm_kanaal(ik.id, jij.id), ik.id) == "Testpersoon Twee"
    assert _label(st, channels.dm_kanaal(ik.id, jij.id), jij.id) == "Testpersoon Een"


def test_het_scherm_belooft_geen_wachtrij_die_niet_bestaat(tmp_path):
    """DEZE TEST STOND OP ZIJN KOP. Hij eiste `"/inbox" in html`: Messages moest naar de wachtrij
    VERWIJZEN, want 338 rol-notificaties zijn werk en geen gesprek.

    Die wachtrij bestaat niet. Er is geen route `/inbox` in `do_GET`, geen `views/inbox.py`, en de
    knop in de zijbalk riep `ibxToggle()` aan — een functie die nergens in de repo staat. De test
    bewaakte dus een link naar een 404, en hield hem daar sinds fase 8 in stand.

    Wat hij nu bewaakt is dezelfde zorg vanaf de andere kant: het scherm mag geen wachtrij
    beloven die er niet is. Komt de functie ooit terug, dan hoort déze assertie te vallen — en dan
    is er ook echt een pagina om naartoe te wijzen (besluit Stefan, 21 september 2026)."""
    from nooch_village.views.messages import render_messages
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    html = render_messages(st, ik=ik.id, csrf_token="t")
    assert "/inbox" not in html
    assert "<nav class='msg-lijst'>" in html      # wat er wél staat: de kanalenlijst


# ── 4. de poort op schrijven ─────────────────────────────────────────────────
def test_schrijven_vraagt_een_herkende_mens(tmp_path):
    dd, st = _stores(tmp_path)
    _, msg = cockpit2.dispatch(dd, "msg_post",
                               {"kanaal": [channels.circle_kanaal(CIRKEL)], "tekst": ["hoi"],
                                "next": ["/"]}, username="guest")
    assert "needs an author" in msg


def test_je_kunt_niet_in_andermans_dm_schrijven(tmp_path):
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    _mens(st, "Testpersoon Twee", "twee@test.nl")
    _mens(st, "Testpersoon Drie", "drie@test.nl")
    vreemd = channels.dm_kanaal("andere-a", "andere-b")
    _, msg = cockpit2.dispatch(dd, "msg_post", {"kanaal": [vreemd], "tekst": ["hoi"], "next": ["/"]},
                               username="een@test.nl")
    assert "not yours" in msg
    assert cockpit2._Stores(dd).channels.trail(vreemd) == []


def test_een_onbekend_kanaal_wordt_geweigerd(tmp_path):
    dd, st = _stores(tmp_path)
    _mens(st, "Testpersoon Een", "een@test.nl")
    _, msg = cockpit2.dispatch(dd, "msg_post", {"kanaal": ["rommel:xyz"], "tekst": ["hoi"],
                                                "next": ["/"]}, username="een@test.nl")
    assert "unknown channel" in msg


# ── 5. zoeken op inhoud ──────────────────────────────────────────────────────
def test_zoek_vindt_gespreksinhoud_en_stappen(tmp_path):
    from nooch_village.views.search import _zoek
    dd, st = _stores(tmp_path)
    ik = _mens(st, "Testpersoon Een", "een@test.nl")
    pid = st.projects.create(OWNER, "Batch 4", "human", status="running")
    st.channels.post(channels.project_kanaal(pid), "Selco levert in drie weken.", author_id=ik.id)
    cl = st.projects.checklist_add(pid, "Stappen")
    st.projects.check_add(pid, cl["id"], "Vraag Selco om een monster")

    res, _fouten = _zoek(cockpit2._Stores(dd), ["selco"])
    soorten = {r["kind"] for groep in res for r in (groep[1] if isinstance(groep, tuple) else [])} \
        if res and isinstance(res[0], tuple) else {r["kind"] for r in res}
    assert "message" in soorten, soorten
    res2, _ = _zoek(cockpit2._Stores(dd), ["monster"])
    soorten2 = {r["kind"] for groep in res2 for r in (groep[1] if isinstance(groep, tuple) else [])} \
        if res2 and isinstance(res2[0], tuple) else {r["kind"] for r in res2}
    assert "step" in soorten2, soorten2


def test_een_prive_gesprek_blijft_buiten_de_zoek(tmp_path):
    """Een DM doorzoekbaar maken voor iedereen die is ingelogd is geen zoekfunctie maar een lek."""
    from nooch_village.views.search import _zoek
    dd, st = _stores(tmp_path)
    a = _mens(st, "Testpersoon Een", "een@test.nl")
    b = _mens(st, "Testpersoon Twee", "twee@test.nl")
    st.channels.post(channels.dm_kanaal(a.id, b.id), "geheimwoord hier", author_id=a.id)
    res, _ = _zoek(cockpit2._Stores(dd), ["geheimwoord"])
    plat = [r for groep in res for r in (groep[1] if isinstance(groep, tuple) else [groep])] \
        if res and isinstance(res[0], tuple) else res
    assert not any("geheimwoord" in str(r.get("snip", "")) for r in plat)
