"""Een vrij label is ook op te ruimen, en heeft ook een naam (27 september 2026).

TWEE DINGEN DIE UIT #616 VOLGDEN, allebei omdat `signaal.stuur` zijn `by` ongefilterd als
`author_id` wegschrijft en `by` vrije tekst is.

1. **OPRUIMEN.** #616 gaf een rol-bericht aan wie de rol bekleedt. Maar 134 van de 374
   rol-berichten op prod dragen een `author_id` die helemaal geen rol is — 'claims-checker' (46),
   'zelf' (20), 'dialoog' (13), 'founder-flow' (7), plus elf met een PERSON-id dat als rol-id is
   weggeschreven. Daar valt niets aan te koppelen, dus bleven ze voor niemand weg te halen: exact
   het probleem dat #616 voor de andere helft oploste. Nu mag de ANCHOR-LEAD ze opruimen — dezelfde
   terugval die `mag_kanaal_verwijderen` al kiest als er geen bekende eigenaar is.

2. **DE NAAM.** `_bericht` zette `wie` op "Someone" zodra de auteur geen mens was. Vier berichten
   van vier afzenders lazen in de kop dus identiek, en je kon niet zien wélke rol iets zei — laat
   staan of het er één was die jij bekleedt, wat sinds #616 het verschil maakt tussen wel en geen
   Remove-knop.

WAT BEWUST NIET MEEVERANDERT: een rol die WEL bestaat maar niemand vervult (188 op prod). Daar is
een eigenaar-bij-regel (CLAUDE.md, "Onbemande rol als signaal": de accountabilities vallen toe aan
de founder), en dat is een bredere regel dan gevraagd. Verwijderen is onomkeerbaar; die keuze is
aan de mens.
"""
from __future__ import annotations

import inspect

from nooch_village import channels, cockpit2
from nooch_village.cockpit2_util import _rol_naam
from nooch_village.views import messages as mv
from nooch_village.views.messages import _afzender, _bericht

def _zonder_uitleg(bron: str) -> str:
    """De CODE van een functie, zonder de docstring. Anders toetst een verbod op een woord net zo
    goed de uitleg waarin dat woord juist hoort te staan — `mag_wissen` legt zelf uit dat hij niets
    van `assignments` weet."""
    if '"""' not in bron:
        return bron
    kop, _doc, rest = bron.split('"""', 2)
    return kop + rest


ROL = "mother_earth__nooch__creator_of_shoes"
ANDERE_ROL = "mother_earth__nooch__compliance"
VRIJ = "claims-checker"


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    baas = st.people.add("Anchor Lead", "anchor@test.nl")
    gewoon = st.people.add("Gewoon Iemand", "gewoon@test.nl")
    st.assign.assign("mother_earth__circle_lead", "person", baas.id)
    st.assign.assign(ROL, "person", gewoon.id)
    return dd, st, baas, gewoon


def _kanaal(st, a, b):
    return channels.dm_kanaal(a, b)


def _rolbericht(st, kanaal, auteur, tekst="een melding"):
    return st.channels.post(kanaal, tekst, author_type="role", author_id=auteur)["id"]


def _wis(st, dd, kanaal, item, email):
    velden = {"kanaal": kanaal, "item": item}
    c = cockpit2._Ctx(st=st, g=lambda k, d="": velden.get(k, d), nxt="/messages",
                      form=velden, username=email, action="msg_remove", data_dir=dd)
    return cockpit2.ACTIONS["msg_remove"](c)


# ══ 1. De anchor-lead ruimt een vrij label op ════════════════════════════════
def test_de_anchor_lead_mag_een_vrij_label_weghalen(tmp_path):
    """DE KERN. 46 van de 374 op prod staan onder precies dit label."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    item = _rolbericht(st, k, VRIJ)
    _nxt, msg = _wis(st, dd, k, item, baas.email)
    assert msg.startswith("🗑")
    assert st.channels.trail(k) == []


def test_elk_vrij_label_telt(tmp_path):
    """'zelf' (20), 'dialoog' (13), 'founder-flow' (7), 'een rol' (5) — geen lijst met bekende
    namen, maar de vraag of er een RECORD achter zit."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    for label in ("zelf", "dialoog", "founder-flow", "een rol", "afslank-opruiming", "dorp"):
        item = _rolbericht(st, k, label)
        _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, baas.email)
        assert msg.startswith("🗑"), label


def test_ook_een_person_id_dat_als_rol_is_weggeschreven(tmp_path):
    """ELF OP PROD. Een person-id met `type='role'` is een datafout, geen rol — dus geen record,
    dus de vrij-label-tak. In #616 kon niemand erbij; nu de anchor-lead."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    item = _rolbericht(st, k, gewoon.id)
    _nxt, msg = _wis(st, dd, k, item, baas.email)
    assert msg.startswith("🗑")


def test_een_gewone_mens_mag_dat_niet(tmp_path):
    """De terugval is de ANCHOR-LEAD, niet "dan maar iedereen". Zou dat laatste gelden, dan is een
    vrij label juist minder beschermd dan een rol-bericht."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    item = _rolbericht(st, k, VRIJ)
    _nxt, msg = _wis(st, dd, k, item, gewoon.email)
    assert msg.startswith("✗")
    assert len(st.channels.trail(k)) == 1


def test_een_circle_lead_van_een_andere_cirkel_ook_niet(tmp_path):
    """Zelfde afweging als bij `mag_kanaal_verwijderen`: een vrij label hangt nergens onder, dus
    "de" Circle Lead bestaat niet."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    st.assign.assign("mother_earth__nooch__circle_lead", "person", gewoon.id)
    k = _kanaal(st, baas.id, gewoon.id)
    item = _rolbericht(st, k, VRIJ)
    _nxt, msg = _wis(cockpit2._Stores(dd), dd, k, item, gewoon.email)
    assert msg.startswith("✗")


def test_een_bestaande_maar_onbemande_rol_valt_er_niet_onder(tmp_path):
    """DE GRENS DIE BEWUST IS GETROKKEN. 188 op prod. Er is een record, dus geen vrij label — en
    de accountability-bij-regel uit CLAUDE.md is een bredere wijziging dan gevraagd."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    item = _rolbericht(st, k, ANDERE_ROL)
    _nxt, msg = _wis(st, dd, k, item, baas.email)
    assert msg.startswith("✗")
    assert len(st.channels.trail(k)) == 1


def test_de_rol_tak_gaat_voor(tmp_path):
    """Bekleed je de rol, dan mag je het sowieso — daar is geen anchor-lead voor nodig."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    item = _rolbericht(st, k, ROL)
    _nxt, msg = _wis(st, dd, k, item, gewoon.email)
    assert msg.startswith("🗑")


def test_andermans_mensbericht_blijft_verboden_ook_voor_de_anchor_lead(tmp_path):
    """DE TERUGVAL RAAKT ALLEEN DE ROL-TAK. Een bericht van een MENS blijft van die mens; anders
    zou de anchor-lead ineens in ieders DM kunnen opruimen."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    e = st.channels.post(k, "van een mens", author_type="human", author_id=gewoon.id)
    _nxt, msg = _wis(st, dd, k, e["id"], baas.email)
    assert msg.startswith("✗")
    assert len(st.channels.trail(k)) == 1


def test_bewerken_blijft_ook_hier_verboden(tmp_path):
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    item = _rolbericht(st, k, VRIJ)
    velden = {"kanaal": k, "item": item, "tekst": "herschreven"}
    c = cockpit2._Ctx(st=st, g=lambda x, d="": velden.get(x, d), nxt="/messages",
                      form=velden, username=baas.email, action="msg_edit", data_dir=dd)
    _nxt, msg = cockpit2.ACTIONS["msg_edit"](c)
    assert msg.startswith("✗")
    assert st.channels.trail(k)[0]["text"] == "een melding"


def test_de_knop_volgt_dezelfde_regel(tmp_path):
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    e = st.channels.post(k, "een melding", author_type="role", author_id=VRIJ)
    assert "value='msg_remove'" in _bericht(st, e, kanaal=k, csrf_token="t", ik=baas.id)
    assert "value='msg_remove'" not in _bericht(st, e, kanaal=k, csrf_token="t", ik=gewoon.id)


def test_mag_wissen_is_niet_aangeraakt():
    """DE REDEN VOOR DEZE VORM. De vraag "wie mag namens deze auteur handelen" zat al in de
    `rol_check`-callable; een tweede parameter of een tri-state erbij zou hetzelfde antwoord op
    twee manieren laten uitdrukken. `channels.py` blijft onwetend van `assignments`."""
    code = _zonder_uitleg(inspect.getsource(channels.mag_wissen))
    for verboden in ("anchor", "circle_lead", "records", "assign"):
        assert verboden not in code, f"{verboden} staat in de CODE van mag_wissen:\n{code}"
    assert "rol_check" in inspect.signature(channels.ChannelStore.verwijder).parameters


def test_de_regel_staat_op_een_plek():
    """`wis_namens` voedt zowel het scherm als de store; hiervoor bouwden die allebei hun eigen
    lambda — twee kopieën van dezelfde regel."""
    assert "wis_namens(st, ik)" in inspect.getsource(cockpit2.mag_bericht_verwijderen)
    assert "wis_namens(st, ik)" in inspect.getsource(cockpit2._act_msg_remove)
    assert "is_role_filler" not in inspect.getsource(cockpit2._act_msg_remove)


def test_het_register_beslist_wat_een_rol_is():
    """Geen naamheuristiek ("bevat een dubbele underscore"), geen lijst met bekende labels."""
    bron = inspect.getsource(cockpit2.wis_namens)
    assert "st.records.get(rid) is None" in bron


# ══ 2. De naam boven het bericht ═════════════════════════════════════════════
def test_een_mens_houdt_zijn_naam(tmp_path):
    dd, st, baas, gewoon = _dorp(tmp_path)
    assert _afzender(st, {"type": "human", "id": gewoon.id}) == "Gewoon Iemand"


def test_een_rol_toont_zijn_rolnaam(tmp_path):
    dd, st, baas, gewoon = _dorp(tmp_path)
    naam = _afzender(st, {"type": "role", "id": ROL})
    assert naam and naam != "Someone"
    assert "creator_of_shoes" not in naam, "dat is het id, niet een naam"


def test_een_vrij_label_toont_zichzelf(tmp_path):
    """"er is dan geen rolnaam om op te zoeken, maar er is wel altijd een niet-lege author_id"."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    for label in ("zelf", "dialoog", "claims-checker", "founder-flow"):
        assert _afzender(st, {"type": "role", "id": label}) == label


def test_someone_blijft_over_voor_een_bericht_zonder_auteur(tmp_path):
    """Het eerlijke antwoord op een ontbrekend veld, en verder niets."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    for a in ({"type": "role", "id": ""}, {"type": "human", "id": ""}, {}):
        assert _afzender(st, a) == "Someone", a


def test_de_rolnaam_onderscheidt_tegen_de_hele_organisatie(tmp_path):
    """`_rol_labels` telt botsingen BINNEN de lijst die je hem geeft. Eén kandidaat botst nooit,
    dus dan krijg je kaal "Circle Lead" terwijl er meerdere zijn. Alle records meegeven is hier
    geen verspilling maar de hele reden dat hij het goede antwoord geeft."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    leads = [r.id for r in st.records.all() if r.id.endswith("__circle_lead")]
    if len(leads) < 2:
        import pytest
        pytest.skip("deze dataset heeft maar één Circle Lead")
    namen = [_rol_naam(st, r) for r in leads]
    assert len(set(namen)) == len(namen), namen


def test_een_onbestaande_rol_valt_terug_op_het_id(tmp_path):
    dd, st, baas, gewoon = _dorp(tmp_path)
    assert _rol_naam(st, "bestaat-niet") == "bestaat-niet"
    assert _rol_naam(st, "") == ""


def test_de_naam_staat_ook_echt_boven_het_bericht(tmp_path):
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    e = st.channels.post(k, "een melding", author_type="role", author_id=VRIJ)
    h = _bericht(st, e, kanaal=k, csrf_token="t", ik=baas.id)
    assert "claims-checker" in h
    assert "Someone" not in h


def test_twee_afzenders_lezen_niet_meer_hetzelfde(tmp_path):
    """HET PROBLEEM IN ÉÉN TOETS. Vier berichten van vier afzenders lazen in de kop identiek."""
    dd, st, baas, gewoon = _dorp(tmp_path)
    k = _kanaal(st, baas.id, gewoon.id)
    koppen = []
    for auteur in (ROL, ANDERE_ROL, VRIJ, "zelf"):
        e = st.channels.post(k, f"melding van {auteur}", author_type="role", author_id=auteur)
        koppen.append(_afzender(st, e["author"]))
    assert len(set(koppen)) == 4, koppen
    assert "Someone" not in koppen


def test_de_view_hergebruikt_de_bestaande_naam_helper():
    """"Hergebruik de bestaande naam-opzoek-helper voor rollen in plaats van een nieuw mechanisme
    te bouwen." Dat is `_rol_labels`, via `_rol_naam` naast `_person_name`."""
    from nooch_village import cockpit2_util
    assert "_rol_labels(" in inspect.getsource(cockpit2_util._rol_naam)
    bron = inspect.getsource(mv)
    assert "_rol_labels" not in bron, "de view bouwt de labels zelf"
    # "Someone" hoort NERGENS ANDERS in de view te staan: één plek waar een afzender een naam
    # krijgt, anders lopen de twee uit elkaar zoals `_person_name` en de kale "Someone" dat deden.
    assert bron.count('"Someone"') == inspect.getsource(mv._afzender).count('"Someone"')
