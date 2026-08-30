"""De verrijking gebeurt bij het ONTSTAAN, niet in een batch.

Eén call per nieuwe spanning: wie hem later opent leest de al-geschreven bevinding en het
al-bepaalde type. De store blijft dom — hij roept alleen een haak aan — zodat er geen model-aanroep
in de opslaglaag belandt.
"""
from __future__ import annotations

from nooch_village import notifications as nm
from nooch_village.spanning_ontstaat import maak_verrijker


class _Def:
    def __init__(self, accs=()):
        self.accountabilities = list(accs)
        self.purpose = ""
        self.domains = []
        self.name = ""


class _Rec:
    def __init__(self, rid, accs=()):
        self.id = rid
        self.definition = _Def(accs)
        self.archived = False


class _Records:
    def __init__(self, recs):
        self._r = {r.id: r for r in recs}

    def get(self, rid):
        return self._r.get(rid)

    def all(self):
        return list(self._r.values())


RECS = _Records([_Rec("compliance", ["Toetsen van publieke claims aan EmpCo"]),
                 _Rec("founder", ["Guarding mission"])])


class _Filler:
    """De echte store geeft objecten met .type, geen dicts — het dubbel doet dat ook, anders test
    je iets anders dan er draait."""
    def __init__(self, type_, id_):
        self.type, self.id = type_, id_


class _Assign:
    def __init__(self, mens_rollen):
        self._m = set(mens_rollen)

    def fillers_of(self, rid, record=None):
        return [_Filler("person", "p1")] if rid in self._m else []


def _llm(spanning, voorstel):
    return lambda p, **kw: ('{"spanning": "' + spanning + '", "voorstel": "' + voorstel + '"}')


GOED = ("Op de veelgestelde-vragenpagina staat dat onze schoenen schoon zijn, zonder dat ergens "
        "staat wat we daarmee bedoelen.", "De zin vervangen door wat we kunnen aantonen.")


def test_een_verse_spanning_krijgt_zijn_bevinding_en_type(tmp_path):
    v = maak_verrijker(RECS, _Assign({"founder"}), str(tmp_path), reason_fn=_llm(*GOED))
    uit = v({"target_type": "role", "target_id": "founder", "by": "compliance",
             "snippet": "⤴ beslissing gevraagd: mag de claim 'clean' live volgens EmpCo?"})
    assert uit["bevinding"]["ok"] and uit["bevinding"]["spanning"].startswith("Op de veelgestelde")
    assert uit["type"] and uit["type_reden"]


def test_de_poort_beslist_wie_verrijkt_wordt_niet_de_verrijker(tmp_path):
    """Dit filter is VERHUISD naar `NotifStore.add` (`_is_mens_lezer`), en dat was de hele fix: het
    hing aan de instantie en stond op 2 van de 7 stores. De verrijker doet nu alleen nog de INHOUD.

    Wie er verrijkt wordt is één vraag, en die hoort op één plek."""
    from nooch_village import notifications as nm
    dd = str(tmp_path)
    # een AI-vervulde rol leest geen postbus → de poort houdt hem tegen
    assert nm._is_mens_lezer({"target_type": "role", "target_id": "compliance"}, dd) is False
    # een onbekend doel ook niet
    assert nm._is_mens_lezer({"target_type": "role", "target_id": ""}, dd) is False
    assert nm._is_mens_lezer({"target_type": "iets", "target_id": "x"}, dd) is False


def test_de_store_roept_de_haak_aan_en_blijft_zelf_dom(tmp_path):
    pad = str(tmp_path / "notifications.json")
    st = nm.NotifStore(pad, verrijker=lambda n: {
        "bevinding": {"ok": True, "spanning": "x", "voorstel": "y"}, "type": "founder"})
    n = st.add("role", "founder", "", by="compliance", snippet="iets")
    assert n["type"] == "founder" and n["bevinding"]["ok"]
    # en het staat ook op schijf, niet alleen in het teruggegeven dict
    assert nm.NotifStore(pad).all()[0]["type"] == "founder"


def test_de_haak_zit_op_de_instantie_niet_op_de_module(tmp_path):
    """Een globale haak lekte naar elke test die de cockpit opstartte: daarna deed élke `add` in
    élke andere test stilletjes een model-aanroep. Een haak die verder reikt dan het object dat hem
    draagt is geen haak maar een verrassing."""
    pad = str(tmp_path / "n.json")
    nm.NotifStore(pad, verrijker=lambda n: {"type": "founder"})
    schoon = nm.NotifStore(pad)                      # een ANDERE store, zonder haak
    n = schoon.add("role", "founder", "", by="x", snippet="iets")
    assert "type" not in n


def test_een_kapotte_haak_verliest_de_spanning_niet(tmp_path, caplog):
    """Een spanning die niet verrijkt kon worden is nog steeds een spanning."""
    pad = str(tmp_path / "notifications.json")

    def _stuk(n):
        raise RuntimeError("model weg")

    with caplog.at_level("WARNING"):
        n = nm.NotifStore(pad, verrijker=_stuk).add("role", "founder", "", by="compliance",
                                                    snippet="iets")
    assert n["snippet"] == "iets" and "bevinding" not in n
    assert "poort op notificatie" in caplog.text
