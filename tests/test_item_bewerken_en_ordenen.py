"""Een checklist-item was alleen weg te gooien. Nu ook bij te schaven en te verslepen.

Wat er op het echte bord van 7 september misging, in drie klachten:

1. **Het hand-off-formulier perste de tekst samen.** `.ck-resolve` stond op `flex:0 0 auto` NAAST
   `.ck-txt`, dus het opengeklapte formulier nam de breedte die het nodig had en de itemtekst
   wikkelde tot één woord per regel. Een formulier hoort een regel niet samen te persen.
2. **`@` gaf geen suggesties.** De datalist droeg kale namen ("Nina"), terwijl de placeholder om een
   `@` vroeg. Een datalist filtert op de WAARDE, dus de eerste toets die je indrukte matchte niets.
3. **Bewerken en herordenen bestonden niet.** Een tikfout herstellen betekende het item verwijderen
   en opnieuw typen — en daarmee ging de skill en de payload die eraan hingen mee weg.

De volgorde is geen smaak: `uitvoerlijst` laat de rol de items van boven naar beneden afwerken. Een
item omhoog slepen betekent dus "dit eerst", en dat was tot nu toe alleen te bereiken door alles
eronder weg te gooien.
"""
from __future__ import annotations

import pytest

from nooch_village.projects import ProjectLedger


@pytest.fixture()
def lijst(tmp_path):
    """Vier items, in bekende volgorde, met een skill op het eerste — zodat een test kan zien of
    bewerken het uitvoer-primitief laat staan."""
    led = ProjectLedger(str(tmp_path / "p.json"))
    pid = led.create("the_source", "doel", "human", status="running")
    cl = led.checklist_add(pid, title="Uitvoerplan")
    led.check_add(pid, cl["id"], "een", skill="web_zoek", payload={"term": "x"})
    for t in ("twee", "drie", "vier"):
        led.check_add(pid, cl["id"], t)
    ids = [it["id"] for it in led.get(pid)["checklists"][0]["items"]]
    return led, pid, cl["id"], ids


def _volgorde(led, pid):
    return [it["text"] for it in led.get(pid)["checklists"][0]["items"]]


# ── Bewerken ─────────────────────────────────────────────────────────────────

def test_bewerken_laat_de_skill_en_payload_staan():
    """DE KERNTEST VAN HET BEWERKEN. Wie een formulering bijschaaft verwacht niet dat hij daarmee de
    skill kwijtraakt. Zou dit het item vervangen in plaats van bewerken, dan kostte elke tikfout een
    uitvoer-primitief — en precies dát was de reden dat mensen items lieten staan zoals ze waren."""
    import tempfile, os
    led = ProjectLedger(os.path.join(tempfile.mkdtemp(), "p.json"))
    pid = led.create("the_source", "doel", "human", status="running")
    cl = led.checklist_add(pid, title="L")
    led.check_add(pid, cl["id"], "suppliers", skill="web_zoek", payload={"term": "soap"})
    iid = led.get(pid)["checklists"][0]["items"][0]["id"]

    assert led.set_item_text(pid, cl["id"], iid, "European suppliers") is True
    it = led.get(pid)["checklists"][0]["items"][0]
    assert it["text"] == "European suppliers"
    assert it["skill"] == "web_zoek"                       # niet weggevallen
    assert it["payload"] == {"term": "soap"}
    assert it["id"] == iid                                 # zelfde item, geen vervanger


def test_lege_tekst_wist_het_item_niet(lijst):
    """Een leeg veld is een vergissing, geen verwijderopdracht. Zou dit doorgaan, dan verdwijnt de
    tekst van een item terwijl het item zelf blijft staan — en dan staat er een naamloze regel die
    niemand meer kan plaatsen."""
    led, pid, clid, ids = lijst
    assert led.set_item_text(pid, clid, ids[0], "   ") is False
    assert _volgorde(led, pid)[0] == "een"


def test_dezelfde_tekst_schrijft_niet(lijst):
    """Geen wijziging → geen touch en geen save. Anders verspringt `updated_at` bij elke keer dat
    iemand het formulier per ongeluk twee keer verstuurt, en dan liegt de sorteervolgorde op het
    bord over wat er recent gebeurd is."""
    led, pid, clid, ids = lijst
    assert led.set_item_text(pid, clid, ids[0], "een") is False


def test_onbekend_item_verandert_niets(lijst):
    led, pid, clid, _ = lijst
    assert led.set_item_text(pid, clid, "bestaatniet", "x") is False
    assert _volgorde(led, pid) == ["een", "twee", "drie", "vier"]


def test_tekst_wordt_gekapt_op_dezelfde_lengte_als_bij_toevoegen(lijst):
    """`check_add` kapt op 200. Zou bewerken dat niet doen, dan is er een achterdeur waarlangs een
    item langer wordt dan via de voordeur kan."""
    led, pid, clid, ids = lijst
    led.set_item_text(pid, clid, ids[0], "x" * 500)
    assert len(led.get(pid)["checklists"][0]["items"][0]["text"]) == 200


# ── Volgorde ─────────────────────────────────────────────────────────────────

def test_omhoog_slepen_zet_het_item_voor_het_anker(lijst):
    led, pid, clid, ids = lijst
    assert led.move_item(pid, clid, ids[2], ids[0]) is True     # 'drie' vóór 'een'
    assert _volgorde(led, pid) == ["drie", "een", "twee", "vier"]


def test_leeg_anker_betekent_naar_het_eind(lijst):
    led, pid, clid, ids = lijst
    assert led.move_item(pid, clid, ids[0], "") is True
    assert _volgorde(led, pid) == ["twee", "drie", "vier", "een"]


def test_item_op_zijn_eigen_plek_schrijft_niet(lijst):
    """`move_item(x, voor=buurman-eronder)` levert dezelfde volgorde op. Zonder deze poort zou elke
    mislukte sleep een save en een `updated_at` opleveren, en dan schuift het project op het bord
    omhoog zonder dat er iets veranderd is."""
    led, pid, clid, ids = lijst
    assert led.move_item(pid, clid, ids[0], ids[1]) is False
    assert _volgorde(led, pid) == ["een", "twee", "drie", "vier"]


def test_op_zichzelf_droppen_doet_niets(lijst):
    led, pid, clid, ids = lijst
    assert led.move_item(pid, clid, ids[1], ids[1]) is False
    assert _volgorde(led, pid) == ["een", "twee", "drie", "vier"]


def test_onbekend_anker_verplaatst_niet_en_verliest_niets(lijst):
    """FAIL-CLOSED, en dit is de test die er echt toe doet. Een vroege versie deed de `pop()` op de
    lijst zelf en zette het item pas terug als het anker onbekend bleek — maar `cl.get("items")`
    geeft de lijst ZELF terug, dus die pop was al een mutatie. Eén verkeerd anker en het item was
    weg. Nu wordt er op een kopie gerekend en pas bij succes toegewezen."""
    led, pid, clid, ids = lijst
    assert led.move_item(pid, clid, ids[0], "bestaatniet") is False
    assert _volgorde(led, pid) == ["een", "twee", "drie", "vier"]     # niets kwijt


def test_verplaatsen_houdt_het_item_intact(lijst):
    """Verhuizen is geen kopiëren: hetzelfde id, dezelfde skill, dezelfde staat."""
    led, pid, clid, ids = lijst
    led.move_item(pid, clid, ids[0], "")
    it = [x for x in led.get(pid)["checklists"][0]["items"] if x["id"] == ids[0]][0]
    assert it["skill"] == "web_zoek" and it["payload"] == {"term": "x"}


def test_verplaatsen_verandert_de_lengte_niet(lijst):
    led, pid, clid, ids = lijst
    for anker in (ids[3], "", ids[0], ids[2]):
        led.move_item(pid, clid, ids[1], anker)
    items = led.get(pid)["checklists"][0]["items"]
    assert len(items) == 4
    assert sorted(x["id"] for x in items) == sorted(ids)


# ── De view: wat de mens ziet ────────────────────────────────────────────────

def _html(led, pid, st=None):
    from nooch_village.views.checklists import _checklists_html
    return _checklists_html(led.get(pid), "csrf-token", pid, "/projects", True, st)


def test_de_at_lijst_draagt_het_apenstaartje():
    """DE OORZAAK VAN 'GEEN SUGGESTIES'. Een datalist filtert op de optie-WAARDE. Stonden daar kale
    namen, dan matcht de `@` die de placeholder vraagt niets en lijkt het veld stuk. De server
    strippen we hem er weer af, dus dit is puur de kant die de mens ziet."""
    import re
    from nooch_village.views import checklists
    bron = open(checklists.__file__, encoding="utf-8").read()
    # De regel die de opties bouwt moet '@' vóór het label zetten.
    m = re.search(r"role_opts\s*=\s*\"\"\.join\(f\"<option value='([^']*)\{_e\(d\['label'\]\)\}",
                  bron)
    assert m, "de optie-bouwer is verplaatst — controleer of het '@' er nog voor staat"
    assert m.group(1) == "@", "zonder '@' in de waarde matcht de datalist niets als je '@' typt"


def test_het_uitklapblok_is_de_details_zelf():
    """De CSS moet op `[open]` kunnen zien dat het paneel openstaat, om het over de volle breedte
    ONDER de tekst te zetten. Zat de klasse op een wikkel eromheen, dan was daar `:has()` voor nodig
    — een omweg om een structuurfout heen."""
    from nooch_village.views import checklists
    bron = open(checklists.__file__, encoding="utf-8").read()
    assert "<details class='fedit ck-resolve'>" in bron
    assert "<span class='ck-resolve'>" not in bron


def test_de_css_zet_een_open_paneel_op_een_eigen_regel():
    """Dit is de klacht van het scherm: de itemtekst wikkelde tot één woord per regel. De regel die
    dat oplost is `flex:1 1 100%` op het OPEN paneel, plus `flex-wrap` op de rij zodat het paneel
    ergens heen kan."""
    import os
    from nooch_village import views
    css = open(os.path.join(os.path.dirname(views.__file__), "..", "static", "nooch.css"),
               encoding="utf-8").read()
    assert ".ck-item{flex-wrap:wrap}" in css
    assert ".ck-resolve[open],.ck-bewerk[open]{flex:1 1 100%" in css
    # `flex-basis:0` op de tekst. Met `auto` is de basismaat de VOLLE tekstbreedte, en zodra de rij
    # mag wrappen springt een lange itemtekst naar een eigen regel ONDER het ✓-vakje. Gevonden door
    # de regel te renderen en op te meten; in de code was het niet te zien.
    assert ".ck-txt{flex:1 1 0}" in css
    # `order:1` houdt de ✕ op de eerste regel. Zonder duwt het 100%-brede paneel hem naar een derde
    # regel, waar hij los onder het formulier hangt.
    assert "order:1" in css.split(".ck-resolve[open]")[1].split("}")[0]
    # De oude regel maakte ELK form doorzichtig, ook het doorgeef-formulier — en dan werkt de
    # flex-indeling van dat formulier niet. De uitzondering moet er staan.
    assert ".ck-item form:not(.ck-doorgeef){display:contents}" in css
    assert "\n.ck-item form{display:contents}" not in css, "de oude, te brede regel staat er nog"
