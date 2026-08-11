"""Domein-drift: een bewaakt domein zonder houder zet stilzwijgend skills uit.

Op productie hield de Librarian het domein `library`, terwijl `seeds.py` `bibliotheek` zaait en
`skill_meta.py` daarop bewaakt. Gevolg: `keyword_review` — en daarmee de hele curatie-lijn —
weigerde elke aanroep met "alleen de domeinhouder mag dat middel voeren", en niemand merkte het.
Het project dat erop wachtte stond vijftien dagen stil.

Dit is dezelfde klasse als de prijsloze ladder-trede: een waarde die op TWEE plekken moet kloppen,
zonder iets dat ze aan elkaar bindt. De domeinnaam staat als string-literal in `skill_meta.META` én
als vrije tekst in een governance-record, en een hernoeming aan één kant meldt zich nergens.

Een uitgezette domein-skill meldt zichzelf niet. Daarom deze guard.
"""
from __future__ import annotations

from nooch_village import skill_meta
from nooch_village.governance import Records
from nooch_village.seeds import seed_records


def _seed_recs(tmp_path):
    recs = Records(str(tmp_path / "governance_records.json"))
    seed_records(recs)
    return recs.all()


def test_elk_bewaakt_domein_heeft_een_houder_in_de_zaad_records(tmp_path):
    """Anders is de skill dood bij oplevering: hij weigert elke aanroep, en het enige spoor is een
    foutregel diep in een puls-log."""
    recs = _seed_recs(tmp_path)
    zonder = {}
    for skill, meta in skill_meta.META.items():
        domein = meta.get("schrijft_in_domein")
        if domein and not skill_meta.domeinhouders(skill, recs):
            zonder[skill] = domein
    assert zonder == {}, (
        "bewaakt domein zonder houder in seeds.py: "
        + "; ".join(f"{s} → '{d}'" for s, d in sorted(zonder.items()))
        + ". Ken het domein toe aan een rol, of lijn de naam uit met het record.")


def test_geen_enkele_zaad_rol_bezit_een_skill_die_hij_niet_mag_voeren(tmp_path):
    """De andere kant van dezelfde munt: een rol mét de skill maar zónder het domein. Dat is precies
    wat de Librarian overkwam — hij bezat `keyword_review` en mocht hem niet draaien."""
    recs = _seed_recs(tmp_path)
    fout = []
    for rec in recs:
        d = getattr(rec, "definition", None)
        for skill in (getattr(d, "skills", None) or []):
            if not skill_meta.schrijft_in_domein(skill):
                continue
            ok, waarom = skill_meta.koppelbaar(skill, rec)
            if not ok:
                fout.append(f"{rec.id}: {waarom}")
    assert fout == [], "\n".join(fout)


def test_de_librarian_houdt_het_bibliotheek_domein(tmp_path):
    """Het concrete geval, apart vastgelegd: de curatie-lijn hangt hieraan. Zonder deze regel is de
    guard hierboven te bevredigen door de skill wég te halen in plaats van het domein te herstellen."""
    recs = _seed_recs(tmp_path)
    lib = next((r for r in recs if r.id == "librarian"), None)
    assert lib is not None
    assert "bibliotheek" in {str(x).lower() for x in (lib.definition.domains or [])}
    assert skill_meta.koppelbaar("keyword_review", lib)[0] is True


def test_domeinhouders_vindt_de_houder_ongeacht_hoofdletters(tmp_path):
    """Domeinen zijn vrije tekst in een record ('Decision Making', 'Copycheck', 'Nooch.earth'), dus
    de vergelijking moet case-ongevoelig zijn. Dat is ze — deze test bevriest dat, want zonder die
    eigenschap ontstaat exact dezelfde stille mismatch met een hoofdletter erin."""
    recs = _seed_recs(tmp_path)
    lib = next(r for r in recs if r.id == "librarian")
    lib.definition.domains = ["Bibliotheek"]
    assert skill_meta.koppelbaar("keyword_review", lib)[0] is True


# ── De runtime-sweep: de pytest-guard ziet alleen seeds.py ──────────────────

def test_de_sweep_vindt_een_domein_zonder_houder(tmp_path):
    """DE fix voor deze klasse. De guard hierboven draait op `seeds.py` en was groen terwijl
    productie stilstond: het record was afgedreven, de code niet. Alleen een sweep over de LEVENDE
    records ziet dat."""
    recs = _seed_recs(tmp_path)
    lib = next(r for r in recs if r.id == "librarian")
    lib.definition.domains = ["library"]                 # de productiestand van 11 aug

    gaten = skill_meta.domein_gaten(recs)
    assert any("bibliotheek" in g and "geen houder" in g for g in gaten), gaten
    assert any("librarian" in g and "keyword_review" in g for g in gaten), gaten


def test_de_sweep_zwijgt_als_alles_klopt(tmp_path):
    assert skill_meta.domein_gaten(_seed_recs(tmp_path)) == []


def test_de_sweep_draait_bij_het_opstarten():
    """Zonder deze bedrading is de sweep dode code — precies zoals de prijs-sweep die lui
    waarschuwde en luna daardoor maanden miste."""
    src = open("nooch_village/village.py", encoding="utf-8").read()
    assert "domein_gaten(self.records.all())" in src and "DOMEIN_GAT" in src


def test_de_sweep_overleeft_een_kapot_record(tmp_path):
    class _Kapot:
        id = "stuk"
        definition = None
    recs = _seed_recs(tmp_path) + [_Kapot()]
    assert skill_meta.domein_gaten(recs) == []
