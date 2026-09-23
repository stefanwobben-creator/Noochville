"""Brok 2: `domain` mag op elk artefact, niet alleen op een policy (23 september 2026).

WAAROM DIT NODIG IS ONDER VARIANT C. Het bakje wordt afgeleid en niet opgeslagen, dus je zou
denken dat het veld dicht kan blijven. Maar stap 1 van de precedentieregel leest juist het EIGEN
domein van een artefact, en dat is de nauwkeurigste bron die er is: een note die expliciet onder
`Decision Making` hangt, hoort daar ook te landen als zijn eigenaar-rol toevallig iets anders doet.

Dat is precies het geval van de drie pagina's die vandaag in Overig vallen. Alle drie hebben een
eigenaar-rol met twee botsende domeinen, en alle drie hebben een bestaand governance-domein dat
hun inhoud wél dekt:

    "How we decide here"     → Decision Making   (hr-organisatie)
    "Decision coach"         → Decision Making   (hr-organisatie)
    "AI design instructions" → Design system     (tech-platform)

Met dit veld open zijn dat dus geen bakje-overrides maar gewone domein-toewijzingen — en dan
verschuiven ze mee als een domein ooit anders geclassificeerd wordt, in plaats van bevroren te
raken op een bakje. `meta["domein"]` blijft bestaan als noodluik voor het geval er géén
governance-domein past; vandaag is dat nergens nodig.

WAT ER NIET MAG VERANDEREN, en daarom hier bevroren:

  1. de VORM VAN EEN ID. `_mint_id` gebruikt `domain` alleen voor policies (`{DOMEINSLUG}-{NNN}`);
     note en tool houden `{TYPE}-{ROLSLUG}-{NNN}`. Zou dat meebewegen, dan kreeg elke nieuwe note
     met een domein ineens een ander soort id dan zijn buren.
  2. de GOVERNANCE-REF blijft betekenen wat hij betekent. `_act_artefact_edit` logt tegen
     `domain:<naam>` als er een domein is en anders tegen `role:<rol>`. Dat blijft zo, en dat is
     hier juist: een note die zichzelf onder een governance-domein hangt, hoort ook tegen dat
     domein gelogd te worden. Het is geen bijwerking maar de bedoeling.
"""
from __future__ import annotations

from nooch_village import cockpit2, domeinen


def _dorp(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    st = cockpit2._Stores(dd)
    return dd, st, st.records.all()[0].id


# ── 1. Het veld staat open ───────────────────────────────────────────────────
def test_een_note_mag_een_domein_dragen(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Hoe we beslissen", domain="Decision Making")
    assert a.domain == "Decision Making"


def test_een_tool_mag_een_domein_dragen(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "tool", title="Coach", url="/x", domain="Decision Making")
    assert a.domain == "Decision Making"


def test_een_policy_houdt_zijn_domein_zoals_altijd(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "policy", title="Geld", domain="Money")
    assert a.domain == "Money"


def test_het_domein_blijft_begrensd_en_geschoond(tmp_path):
    """Zelfde grenzen als bij een policy: 60 tekens, randen eraf. Een veld dat voor één soort
    begrensd is en voor een andere niet, is een gat dat je pas ziet als iemand erin valt."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="X", domain="  " + "D" * 80 + "  ")
    assert len(a.domain) == 60 and a.domain == "D" * 60


# ── 2. Wat bevroren blijft ───────────────────────────────────────────────────
def test_een_domein_verandert_de_vorm_van_een_note_id_niet(tmp_path):
    """`_mint_id` mag `domain` alleen voor policies gebruiken. Anders krijgt een note met een
    domein ineens een `{DOMEINSLUG}-{NNN}`-id en zijn buurman niet."""
    dd, st, rol = _dorp(tmp_path)
    zonder = st.att.add(rol, "note", title="A")
    met = st.att.add(rol, "note", title="B", domain="Decision Making")
    assert zonder.id.startswith("NOTE-") and met.id.startswith("NOTE-")
    assert "DECISION" not in met.id, "het domein lekt in het id"


def test_een_policy_id_blijft_wel_op_zijn_domein_gebaseerd(tmp_path):
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "policy", title="Geld", domain="Money")
    assert a.id.startswith("MONEY-")


def test_de_governance_ref_volgt_het_domein_als_dat_er_is():
    """Dit is GEEN bijwerking maar de bedoeling: een artefact dat zichzelf onder een
    governance-domein hangt, hoort ook tegen dat domein gelogd te worden. De regel stond er al
    voor policies; hij blijft precies zoals hij is."""
    import inspect
    bron = inspect.getsource(cockpit2._act_artefact_edit)
    assert 'f"domain:{cur.domain}"' in bron
    assert 'f"role:{cur.anchor}"' in bron


# ── 3. Samen met de classificatie uit brok 1 ─────────────────────────────────
def test_een_eigen_domein_wint_van_dat_van_de_rol(tmp_path):
    """DE HELE REDEN DAT DIT VELD OPEN MOEST. De eigenaar-rol hier zou iets anders zeggen; het
    artefact zelf is specifieker en wint."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Hoe we beslissen", domain="Decision Making")
    bak, waarom = domeinen.bakje_van(a, st.records.all())
    assert bak == "hr-organisatie"
    assert "Decision Making" in waarom


def test_de_drie_botsers_zijn_hiermee_op_te_lossen(tmp_path):
    """De drie pagina's die op prod in Overig vallen, met hun échte botsende roldomeinen. Zonder
    eigen domein blijven ze Overig; mét het domein dat hun inhoud dekt, landen ze goed."""
    dd, st, rol = _dorp(tmp_path)
    recs = st.records.all()

    # `type` is hier een ATTRIBUUTNAAM (org.is_circle leest hem) én de builtin waarmee ik de
    # definitie maak. Eerst de definitie bouwen, dan pas het attribuut zetten.
    _definitie = type("D", (), {"domains": ["bibliotheek", "onderzoeksmethode"]})()

    class _Rol:
        id, parent, archived = "botser", None, False
        definition = _definitie
    _Rol.type = "role"

    recs = recs + [_Rol()]
    kaal = st.att.add(rol, "note", title="How we decide here")
    kaal.anchor = "botser"
    assert domeinen.bakje_van(kaal, recs)[0] == "overig"

    kaal.domain = "Decision Making"
    bak, _ = domeinen.bakje_van(kaal, recs)
    assert bak == "hr-organisatie", "met een eigen domein hoort de botsing niet meer te tellen"


def test_zonder_domein_blijft_alles_zoals_het_was(tmp_path):
    """Het openzetten van het veld mag op zichzelf niets verschuiven: wie niets invult, loopt nog
    steeds via de rol."""
    dd, st, rol = _dorp(tmp_path)
    a = st.att.add(rol, "note", title="Gewoon")
    assert a.domain == ""
    bak, waarom = domeinen.bakje_van(a, st.records.all())
    assert "eigen domein" not in waarom
