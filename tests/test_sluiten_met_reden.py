"""De vierde uitkomst: sluiten — en sinds Decide-now weg is draagt hij een reden.

WAT ER WEGGING EN WAAROM. "Decide now" was een eigen knoppenrij (ja / nee / suggestie) op de
inbox-kaart. Gemeten op prod: 12 keer gebruikt op 570 notificaties, 2,1%. Belangrijker dan het
percentage was de VORM van die twaalf:

    9x  een antwoord waarmee een vastgelopen bewoner verder kon      → dat is een ACTIE (flow 1)
    2x  akkoord op een voorstel ("doe de 3-puntsfix")                → ook een actie
    1x  "✗ NEE — ik denk dat hiermee verkeerde doelgroep aantrekken" → géén van de drie flows

De negen (plus de twee akkoorden) lopen nu via flow 1, met de AI-rol als ontvanger waar nodig:
`route_werk` maakt daar een project van, want een AI-rol leest de NotifStore nooit.

De tiende vorm paste nergens, en dat is geen toeval: actie, project en governance veronderstellen
alle drie dát er iets gebeurt. "Nee, want …" is precies het tegendeel. Die hoort bij de uitkomst die
er altijd al was — sluiten — en die krijgt daarom een optioneel reden-veld.

DE HARDE EIS: de reden gaat TERUG naar de vrager. Alleen opslaan zou de terugkoppeling stil laten
verdwijnen die Decide-now's "nee" wél gaf — dezelfde stille degradatie als de "iedereen"-tekst op de
wall, die beloofde te versturen en niets deed.
"""
from __future__ import annotations

import types

from nooch_village import cockpit2
from nooch_village.notifications import NotifStore
from nooch_village.projects import ProjectLedger


def _opzet(tmp_path):
    pj = ProjectLedger(f"{tmp_path}/projects.json")
    pid = pj.create("website_watcher", "Bezoekersdaling duiden", "human")
    entry = pj.add_feed_entry(
        pid, "@The Source — SPANNING: bezoekers 114→73. WAT IK NODIG HEB: kies A of B.",
        kind="comment", author_type="role", author_id="website_watcher")
    notif = NotifStore(f"{tmp_path}/notifications.json", verrijker=lambda n: {})
    n = notif.add("role", "the_source", pid, entry["id"], by="Walter Website",
                  snippet="bezoekers 114→73 — kies A of B")
    st = types.SimpleNamespace(
        notif=notif, projects=pj,
        records=types.SimpleNamespace(get=lambda rid: None),
        people=types.SimpleNamespace(by_email=lambda e: None))
    return st, pj, pid, n


def _sluit(st, pj, n, reden=""):
    c = types.SimpleNamespace(st=st, pj=pj, username="guest", nxt="/inbox",
                              g=lambda k, _v={"nid": n["id"]}: {"nid": n["id"], "reden": reden}.get(k, ""))
    return cockpit2._act_notif_klaar(c)


def test_de_reden_landt_bij_de_vrager(tmp_path):
    """DE HARDE EIS. Opslaan is niet genoeg: wie het vroeg moet het "nee, want" zien."""
    st, pj, pid, n = _opzet(tmp_path)
    _sluit(st, pj, n, reden="niet doen — hiermee trekken we de verkeerde doelgroep aan")
    feed = pj.get(pid).get("log") or []
    teksten = " ".join(str(e.get("text") or "") for e in feed)
    assert "verkeerde doelgroep" in teksten, "de reden kwam niet terug op de bron-feed"


def test_de_reden_komt_van_een_mens_zodat_de_bewoner_hem_oppakt(tmp_path):
    """`comment` + `human` zet `worked=False`: de bewoner pakt zijn eigen spanning weer op. Precies
    het mechaniek dat Decide-now's antwoord gebruikte — niet een tweede kanaal ernaast."""
    st, pj, pid, n = _opzet(tmp_path)
    _sluit(st, pj, n, reden="niet doen")
    feed = pj.get(pid).get("log") or []
    mens = [e for e in feed if (e.get("author") or {}).get("type") == "human"]
    assert mens, "de reden staat niet als menselijke reactie in de feed"
    assert (mens[-1].get("kind") or "") == "comment"
    assert pj.get(pid).get("worked") is False, "de bewoner pakt het niet opnieuw op"


def test_de_reden_staat_ook_in_het_verwerk_record(tmp_path):
    """Terugkoppelen én vastleggen: de raadsvergadering leest later WAAROM iets dichtging."""
    st, pj, pid, n = _opzet(tmp_path)
    _sluit(st, pj, n, reden="niet doen — verkeerde doelgroep")
    verw = st.notif.verwerkingen_of(st.notif._find(n["id"]))
    assert verw and "verkeerde doelgroep" in str(verw[-1].get("label"))
    assert verw[-1].get("otype") == "geen_uitkomst_met_reden"


def test_sluiten_zonder_reden_blijft_gewoon_sluiten(tmp_path):
    """De reden is OPTIONEEL. Een FYI-klep dichtdoen mag zonder verantwoording — anders wordt
    opruimen duur en blijft de inbox vol."""
    st, pj, pid, n = _opzet(tmp_path)
    _sluit(st, pj, n)
    verw = st.notif.verwerkingen_of(st.notif._find(n["id"]))
    assert verw and verw[-1].get("label") == "geen uitkomst"
    feed = pj.get(pid).get("log") or []
    assert not [e for e in feed if (e.get("author") or {}).get("type") == "human"]


def test_zonder_bron_sluit_hij_stil(tmp_path):
    """Fail-soft: geen bron-project = niemand om iets aan terug te koppelen. Sluiten moet dan nog
    steeds werken; een reden zonder ontvanger mag geen fout opleveren."""
    st, pj, pid, n = _opzet(tmp_path)
    los = st.notif.add("role", "the_source", "", by="x", snippet="losse spanning")
    _, msg = _sluit(st, pj, los, reden="niet doen")
    assert "✓" in msg
