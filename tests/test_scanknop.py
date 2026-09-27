"""De scanknop op de handboek-pagina — en het slot eromheen (28 september 2026).

DIT DOORBREEKT EEN BESTAAND ONTWERP, bewust en met één knop (besluit Stefan). `site_audit` en zijn
view waren expliciet alleen-lezen: "dit scherm leest alleen: de run gebeurt via `village
site_audit`". Wat die regel beschermde was niet het LEZEN maar twee andere dingen, en die worden
hier geadresseerd in plaats van weggeredeneerd:

  1. DE DUUR. Een run doet echte netwerkchecks (een GET op de shop, Lighthouse via PageSpeed) en
     duurt 20 tot 60 seconden. Een POST die zo lang openstaat geeft een pagina die hangt zonder te
     zeggen waarom, houdt een serverthread bezet en loopt tegen elke proxy-timeout aan. Daarom
     draait hij in een achtergrondthread en ververst het paneel zichzelf.
  2. DE GELIJKTIJDIGHEID. Er zijn nu drie ingangen (CLI, knop, en de weekklok van scope 47). Twee
     scans tegelijk is niet "dubbel werk" maar vuile data: allebei schrijven ze een snapshot in
     dezelfde append-only reeks, en `verschil()` vergelijkt met de laatste — dus er verschijnt een
     "wissel" tussen twee metingen van dezelfde minuut. Het slot zit daarom in `run_en_bewaar`
     zelf, niet bij een van de aanroepers.
"""
from __future__ import annotations

import inspect
import json
import os
import time

from nooch_village import cockpit2, site_audit
from nooch_village.views.site_audit import scan_paneel
from nooch_village.views.wiki import render_pagina

ROL = "mother_earth__nooch__website_developer"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    baas = st.people.add("Stefan", "stefan@test.nl")
    buiten = st.people.add("Buitenstaander", "buiten@test.nl")
    st.assign.assign(ROL, "person", baas.id)
    return dd, st, baas, buiten


def _pagina(st, body="Zie [Site audit](/site-audit)."):
    return st.att.add(ROL, "note", title="Handboek-proef", body=body)


# ══ 1. Het slot ══════════════════════════════════════════════════════════════
def test_twee_keer_pakken_lukt_maar_een_keer(tmp_path):
    """DE RACE, en niet de vorm ervan: `O_CREAT | O_EXCL` slaagt bij precies één van twee."""
    dd, st, baas, buiten = _dorp(tmp_path)
    assert site_audit._neem_slot(dd, "live", "een") is True
    assert site_audit._neem_slot(dd, "live", "twee") is False
    site_audit._geef_slot(dd, "live")
    assert site_audit._neem_slot(dd, "live", "drie") is True


def test_het_slot_zegt_wie_en_sinds_wanneer(tmp_path):
    dd, st, baas, buiten = _dorp(tmp_path)
    site_audit._neem_slot(dd, "live", "Stefan")
    staat = site_audit.slot_staat(dd)
    assert staat and staat["door"] == "Stefan" and time.time() - staat["sinds"] < 5


def test_een_achtergebleven_slot_blokkeert_niet_voor_altijd(tmp_path):
    """Eén hard gesneuveld proces mag de knop niet tot de volgende deploy dood leggen."""
    dd, st, baas, buiten = _dorp(tmp_path)
    with open(site_audit.slot_pad(dd, "live"), "w", encoding="utf-8") as fh:
        json.dump({"sinds": time.time() - site_audit.SLOT_VERVALT_S - 1, "door": "zombie"}, fh)
    assert site_audit.slot_staat(dd) is None
    assert site_audit._neem_slot(dd, "live", "nieuw") is True


def test_de_twee_doelen_hebben_hun_eigen_slot(tmp_path):
    """`live` en `dev` zijn twee reeksen; een dev-run hoort een live-run niet tegen te houden."""
    dd, st, baas, buiten = _dorp(tmp_path)
    assert site_audit._neem_slot(dd, "live", "a") is True
    assert site_audit._neem_slot(dd, "dev", "b") is True


def test_het_slot_zit_in_de_run_en_niet_bij_de_aanroeper():
    """DE REDEN DAT DIT WERKT VOOR ALLE DRIE DE INGANGEN. Een slot per ingang beschermt alleen
    tegen zichzelf: een klik tijdens een CLI-run zou dan gewoon een tweede scan starten."""
    bron = inspect.getsource(site_audit.run_en_bewaar)
    assert "_neem_slot" in bron and "ScanDraaitAl" in bron
    assert "_geef_slot" in inspect.getsource(site_audit.start_achtergrond)


def test_een_tweede_run_wordt_geweigerd_en_niet_stilletjes_overgeslagen(tmp_path):
    """Fail-loud: `run_en_bewaar` gooit, zodat de CLI het kan zeggen in plaats van te doen alsof."""
    dd, st, baas, buiten = _dorp(tmp_path)
    site_audit._neem_slot(dd, "live", "een ander")
    st.dd = dd
    try:
        site_audit.run_en_bewaar(st, None, None)
    except site_audit.ScanDraaitAl as exc:
        assert "een ander" in str(exc)
    else:                                               # pragma: no cover
        raise AssertionError("de tweede run mocht gewoon door")


def test_het_slot_gaat_ook_terug_als_de_run_klapt(tmp_path):
    """Een netwerkfout hoort de knop geen kwartier dood te leggen."""
    dd, st, baas, buiten = _dorp(tmp_path)
    st.dd = dd
    try:
        site_audit.run_en_bewaar(st, None, None)        # `draai` klapt op None
    except Exception:                                   # noqa: BLE001
        pass
    assert site_audit.slot_staat(dd) is None


# ══ 2. De knop ═══════════════════════════════════════════════════════════════
def _klik(st, dd, username):
    velden = {"csrf": "T", "next": "/pagina?id=X"}
    ctx = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/pagina?id=X",
                        form=velden, username=username, action="site_audit_run", data_dir=dd)
    return cockpit2.ACTIONS["site_audit_run"](ctx)


def test_de_knop_trapt_de_bestaande_ingang_af():
    """"Geen nieuwe scanlogica bouwen." `start_achtergrond` draait dezelfde `_draai_met_slot` als
    `run_en_bewaar`, dus dezelfde checks, drempels en append-only reeks."""
    assert "_draai_met_slot" in inspect.getsource(site_audit.start_achtergrond)
    assert "_draai_met_slot" in inspect.getsource(site_audit.run_en_bewaar)
    assert "def draai(" not in inspect.getsource(site_audit.start_achtergrond)


def test_hij_wacht_niet_op_de_scan(tmp_path, monkeypatch):
    """DE TWEEDE HELFT VAN HET ONTWERP. De POST hoort binnen milliseconden terug te zijn; de scan
    duurt tientallen seconden. Gemeten met een trage nep-run, niet beweerd — en met een nep-run
    omdat de echte `draai` het internet op gaat, en een toets die dat doet meet de dag en niet de
    code.

    HET SLOT WORDT HIER ÉCHT GEPAKT (dat zit vóór de thread), dus dit toetst meteen dat de knop
    "bezig" is zolang de nep-run loopt."""
    dd, st, baas, buiten = _dorp(tmp_path)
    bezig = []

    def _traag(*a, **kw):
        bezig.append(time.time())
        time.sleep(1.5)
        return {}, []

    monkeypatch.setattr(site_audit, "_draai_met_slot", _traag)
    start = time.time()
    pad, melding = _klik(st, dd, "stefan@test.nl")
    duur = time.time() - start
    assert duur < 0.5, f"de POST bleef {duur:.1f}s hangen"
    assert melding.startswith("🔎") and "20-60" in melding
    time.sleep(.3)
    assert bezig, "de scan is helemaal niet gestart"
    assert site_audit.slot_staat(dd) is not None, "het slot staat niet aan tijdens de run"
    time.sleep(1.6)
    assert site_audit.slot_staat(dd) is None, "het slot is na afloop niet teruggegeven"


def test_de_echte_scan_wordt_niet_aangeroepen_in_deze_toetsen(tmp_path, monkeypatch):
    """VANGNET VOOR DE SUITE ZELF. `start_achtergrond` draait een thread die het internet op gaat;
    een toets die dat per ongeluk doet is traag, flaky en belt een externe API. Deze toets legt
    vast dat de knop-tak via `_draai_met_slot` loopt, zodat een stub hem altijd kan onderscheppen."""
    dd, st, baas, buiten = _dorp(tmp_path)
    geraakt = []
    monkeypatch.setattr(site_audit, "_draai_met_slot", lambda *a, **kw: geraakt.append(1) or ({}, []))
    _klik(st, dd, "stefan@test.nl")
    time.sleep(.4)
    assert geraakt == [1]


def test_een_tweede_klik_start_geen_tweede_scan(tmp_path):
    dd, st, baas, buiten = _dorp(tmp_path)
    site_audit._neem_slot(dd, "live", "de weekklok")
    _pad, melding = _klik(st, dd, "stefan@test.nl")
    assert melding.startswith("⏳") and "de weekklok" in melding


def test_wie_de_rol_niet_vervult_mag_niet_scannen(tmp_path):
    """De site audit is het gereedschap van de Website Developer; een run kost een externe
    API-aanroep en schrijft in een reeks waar anderen conclusies uit lezen."""
    dd, st, baas, buiten = _dorp(tmp_path)
    try:
        _klik(st, dd, "buiten@test.nl")
    except cockpit2.Forbidden:
        pass
    else:                                               # pragma: no cover
        raise AssertionError("een buitenstaander mocht scannen")
    assert site_audit.slot_staat(dd) is None, "er is toch een scan gestart"


# ══ 3. Het paneel ════════════════════════════════════════════════════════════
def test_de_pagina_die_de_audit_noemt_krijgt_de_knop(tmp_path):
    """DE KOPPELING IS DE VERWIJZING, niet een titel of een artefact-id — zelfde idioom als de
    decision coach. Haal je de regel uit de pagina, dan is de knop weg."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = _pagina(st)
    h = render_pagina(st, a.id, "TOK", "stefan@test.nl")
    assert "id='scan-paneel'" in h and "value='site_audit_run'" in h


def test_een_pagina_zonder_die_verwijzing_krijgt_niets(tmp_path):
    dd, st, baas, buiten = _dorp(tmp_path)
    a = _pagina(st, body="Gewone tekst zonder verwijzing.")
    assert "scan-paneel" not in render_pagina(st, a.id, "TOK", "stefan@test.nl")


def test_wie_niet_mag_ziet_de_stand_maar_niet_de_knop(tmp_path):
    """Lezen is vrij; starten niet. Een knop tonen die de server daarna weigert is precies wat deze
    codebase elders al heeft opgeruimd."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = _pagina(st)
    h = render_pagina(st, a.id, "TOK", "buiten@test.nl")
    assert "id='scan-paneel'" in h and "value='site_audit_run'" not in h


def test_het_paneel_zegt_dat_er_een_scan_loopt(tmp_path):
    """"laat zien dat hij loopt in plaats van de pagina te laten hangen zonder feedback"."""
    dd, st, baas, buiten = _dorp(tmp_path)
    site_audit._neem_slot(dd, "live", "Stefan")
    h = scan_paneel(dd, "TOK", mag=True)
    assert "scanning" in h and "Stefan" in h
    assert "site_audit_run" not in h, "een startknop terwijl hij al draait"


def test_een_mislukte_scan_leest_niet_als_er_is_niets_gebeurd(tmp_path):
    """Een achtergrondthread heeft geen scherm om op te vallen. Zonder dit tweede spoor is een
    mislukte scan niet te onderscheiden van niet geklikt hebben."""
    dd, st, baas, buiten = _dorp(tmp_path)
    site_audit._noteer_fout(dd, "live", "ConnectionError: geen netwerk")
    h = scan_paneel(dd, "TOK", mag=True)
    assert "failed" in h and "geen netwerk" in h
    assert site_audit.laatste_fout(dd) is not None


def test_een_geslaagde_run_wist_de_foutmelding(tmp_path):
    """Anders blijft er een waarschuwing staan over iets dat allang weer werkt."""
    dd, st, baas, buiten = _dorp(tmp_path)
    site_audit._noteer_fout(dd, "live", "kapot")
    site_audit._wis_fout(dd, "live")
    assert site_audit.laatste_fout(dd) is None
    assert "failed" not in scan_paneel(dd, "TOK", mag=True)


def test_het_paneel_ververst_zichzelf(tmp_path):
    """Zonder poller blijft "scanning…" staan tot de lezer zelf ververst — dan is de knop wél
    veilig maar de terugkoppeling nutteloos."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = _pagina(st)
    h = render_pagina(st, a.id, "TOK", "stefan@test.nl")
    assert "data-poll='/scan-status" in h and "data-poll-ms=" in h


def test_de_poller_is_generiek_en_beschaafd():
    """Eén poller voor twee plekken, met dezelfde drie manieren als de bestaande: niets vragen met
    een verborgen tabblad, bij een fout verdubbelen, en niets vervangen als er niets veranderde."""
    import pathlib
    js = (pathlib.Path(__file__).resolve().parents[1]
          / "nooch_village" / "static" / "nooch.js").read_text(encoding="utf-8")
    blok = js.split("function pollers(")[1].split("\n  function ")[0]
    assert "document.hidden" in blok
    assert "Math.min(wacht * 2" in blok
    assert "html !== el.innerHTML" in blok
    assert "visibilitychange" in blok


def test_de_route_rendert_hetzelfde_fragment():
    """Twee renderers voor één toestand lopen uiteen zodra er één verandert."""
    bron = inspect.getsource(cockpit2.ServerHandler.do_GET) if hasattr(cockpit2, "ServerHandler") \
        else inspect.getsource(cockpit2)
    assert "scan_paneel(" in bron and '"/scan-status"' in bron


# ══ 4. Het scherm /site-audit blijft zoals het was ════════════════════════════
def test_het_auditscherm_trapt_nog_steeds_niets_af(tmp_path):
    """"dat scherm blijft zoals het is." De knop hoort op de handboek-pagina."""
    from nooch_village.views.site_audit import render_site_audit
    dd, st, baas, buiten = _dorp(tmp_path)
    h = render_site_audit(st)
    assert "site_audit_run" not in h and "Run scan" not in h


# ══ 5. De verwijzing in het handboek ═════════════════════════════════════════
def test_het_handboek_krijgt_de_verwijzing_eenmalig(tmp_path):
    """De koppeling moet ÍN de pagina staan, anders draagt hij de knop niet. Eén regel, één keer."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title=site_audit.HANDBOEK_TITEL, body="Bestaande tekst.",
                   url="https://docs.google.com/x", actor_id="iemand", actor_type="person")
    assert site_audit.zorg_voor_knop_verwijzing(st.att) == a.id
    na = st.att.get(a.id)
    assert na.body.startswith("Bestaande tekst."), "de bestaande tekst is aangetast"
    assert "/site-audit" in na.body
    assert site_audit.zorg_voor_knop_verwijzing(st.att) == "", "hij schrijft er nog een bij"


def test_hij_schrijft_niet_in_een_lege_pagina(tmp_path):
    """Een lege pagina vullen is geen koppeling leggen maar schrijven, en dat is niet aan het dorp."""
    dd, st, baas, buiten = _dorp(tmp_path)
    st.att.add(ROL, "tool", title=site_audit.HANDBOEK_TITEL, body="", url="https://x")
    assert site_audit.zorg_voor_knop_verwijzing(st.att) == ""


def test_hij_raakt_geen_andere_pagina_aan(tmp_path):
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title="Iets anders", body="Tekst.", url="https://x")
    site_audit.zorg_voor_knop_verwijzing(st.att)
    assert st.att.get(a.id).body == "Tekst."


def test_de_wijziging_staat_in_de_historie(tmp_path):
    """Een machinale bewerking van andermans tekst hoort terug te vinden te zijn, met de reden."""
    dd, st, baas, buiten = _dorp(tmp_path)
    a = st.att.add(ROL, "tool", title=site_audit.HANDBOEK_TITEL, body="Tekst.", url="https://x")
    site_audit.zorg_voor_knop_verwijzing(st.att)
    laatste = st.att.get(a.id).versions[-1]
    assert laatste["actor_id"] == "system"
    assert "scanknop" in (laatste.get("change_note") or "")
