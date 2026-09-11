"""Eén memo van Noochie aan de founder, op afroep — de toets van de pijp, en sinds 42a: de inhoud.

Aanleiding (11 september 2026). Stefan zag nooit iets van Noochie en dacht aan de verkeerde inbox.
Gemeten: er wás geen inbox. Het dagbulletin ging naar schijf en naar een logger, en verder nergens.
De eerste memo die wél aankwam was een organisatie-overzicht ("17 van de 127 projecten staan
vast"), want ze kreeg alleen tellingen en titels. Dezelfde middag: "ik mis dat ie inhoudelijk
meedenkt."

Wat hier vastligt:

1. De memo komt via de bestaande founder-route (`_notify_founder` → `("role", FOUNDER_ROLE_ID)`)
   met afzender `noochie` en de tekst ONGEWIJZIGD. Die laatste is de scherpe: `NotifStore.add`
   stuurt een item zonder type door een herschrijf-poort die niet-menselijke tekst met een goedkoop
   model herformuleert. Voor een memo is dat verminking onder Noochie's naam.
2. Zonder LLM-antwoord: geen memo en geen bezorging. Nooit een sjabloon alsof zij hem schreef.
3. De invoer is de INHOUD: comments van mensen, het log, het uitvoerplan met wat elk item echt
   opleverde, bijlagen met pdf-tekst, de wiki, de claims per status. Niet eerdere LLM-tekst, en
   niet haar eigen oude ruis uit de gesloopte matchlaag.
4. Precies één LLM-call, op de hoog-inzet-site.
5. De memo is in de inbox een DOCUMENT: markdown met codeblokken, en de commando-swap blijft eraf,
   want een opdracht om te plakken is precies wat de founder vroeg.
"""
from __future__ import annotations

import io
import json
import os
import time
from unittest import mock

from nooch_village import cockpit2, noochie_memo
from nooch_village.human_inbox import FOUNDER_ROLE_ID

MEMO = ("Mobiel · Leveranciers in Spanje\n\n"
        "### Mobiel\n**Wat ik zie**: het project zit vast op een audit.\n"
        "**Wat jij nu kunt doen**:\n```\nMaak village.nooch.earth mobielvriendelijk.\n"
        "Toets: python -m pytest tests/\n```\n\n"
        "### Leveranciers in Spanje\n**Wat ik zie**: Cristian is afgevallen, Mees loopt.\n\n"
        "**Wat ik niet weet**\n- de MOQ van Mees")

ROL = "mother_earth__nooch__website_developer"


def _st(tmp_path):
    dd = str(tmp_path / "poc")
    cockpit2._bootstrap(dd)
    return dd, cockpit2._Stores(dd)


def _founder_items(dd):
    return cockpit2._Stores(dd).notif.for_targets([("role", FOUNDER_ROLE_ID)])


def _project(st, titel, *, status="running", owner=ROL):
    pid = st.projects.create(owner, titel, "human", status="queued")
    if status in ("running", "blocked", "done"):
        st.projects.start(pid)
    if status == "blocked":
        st.projects.block(pid, on_role="mother_earth__nooch__creator_of_shoes")
    if status == "done":
        st.projects.complete(pid, "approved after review")
    return pid


def _mini_pdf(tekst: str) -> bytes:
    """Een geldige één-pagina-pdf met Helvetica-tekst, zonder bibliotheek: genoeg voor pypdf."""
    woorden, regels, regel = tekst.split(), [], ""
    for w in woorden:
        if len(regel) + len(w) + 1 > 80:
            regels.append(regel); regel = w
        else:
            regel = f"{regel} {w}".strip()
    regels.append(regel)

    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    inhoud = "BT /F1 11 Tf 40 780 Td 14 TL " + " ".join(f"({esc(r)}) Tj T*" for r in regels) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(inhoud.encode('latin-1'))} >>\nstream\n{inhoud}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


# ── verzamelen ───────────────────────────────────────────────────────────────

def test_verzamelen_is_rauw_en_faalt_per_bron(tmp_path):
    dd, st = _st(tmp_path)
    f = noochie_memo.verzamel(st, dd)
    assert set(f) >= {"datum", "projecten", "claims", "wiki", "events", "gereedschap", "werkoverleg_backlog"}
    assert f["claims"]["werklijst"] == 20 and f["claims"]["per_status"] == {"open": 20}   # de seed
    assert f["projecten"]["totaal"] == 0 and f["projecten"]["inhoud"] == []               # geen projecten
    assert f["events"]["regels"] == 0                                                     # geen log


def test_de_prompt_bevat_de_inhoud_en_geen_eerdere_llm_tekst(tmp_path):
    dd, st = _st(tmp_path)
    p = noochie_memo.prompt_voor(noochie_memo.verzamel(st, dd))
    assert "INHOUD (JSON)" in p and '"werklijst": 20' in p
    assert "field_note" not in p.lower() and "bulletin" not in p.lower()
    assert "Claude Code" in p and "onderwerpregel" in p       # het artefact en de preview-regel


def test_claims_per_status_niet_alleen_open(tmp_path):
    """Op de server stond de hele werklijst op `in behandeling`/`live`; met alleen een open-telling
    zag Noochie '0 open' en schreef 'óf klaar, óf niet bijgehouden'. Een artefact van de feed."""
    from nooch_village import claims_db
    dd, st = _st(tmp_path)
    claims_db.overlay_set_status(dd, 1, "live")
    claims_db.overlay_set_status(dd, 2, "in behandeling")
    c = noochie_memo.verzamel(st, dd)["claims"]
    assert c["per_status"] == {"open": 18, "live": 1, "in behandeling": 1}
    assert set(c["voorbeelden_per_status"]) == {"open", "live", "in behandeling"}
    assert "2024/825" in c["handhaving"]


# ── de inhoud van een project ────────────────────────────────────────────────

def test_projectinhoud_comments_log_uitvoerplan_en_blokkade(tmp_path):
    """Het mobiel-geval van 11 september: 'vastgelopen op 1 item, wacht op een mens' zegt niets;
    het uitvoerplan zegt wát dat item is en dat een afgevinkte meting leeg was (93 tekens)."""
    dd, st = _st(tmp_path)
    pid = _project(st, "village.nooch.earth is mobile friendly", status="blocked")
    st.projects.add_comment(pid, "eerst kijken of de header op een telefoon past")
    cl = st.projects.checklist_add(pid, "Uitvoerplan")
    clid = cl["id"]
    st.projects.check_add(pid, clid, "Haal de pagina op en zoek naar viewport", skill="haal_pagina",
                          payload={"url": "https://village.nooch.earth"})
    st.projects.check_add(pid, clid, "Voer een technische audit uit van CSS/HTML-broncode",
                          reason="geen skill voor broncode-analyse")
    items = st.projects.get(pid)["checklists"][0]["items"]
    st.projects.check_toggle(pid, clid, items[0]["id"])
    st.projects.set_item_leeg(pid, clid, items[0]["id"],
                              reden="term 'viewport' komt niet voor op deze pagina (93 tekens gelezen)")
    st.projects.set_item_human(pid, clid, items[1]["id"])
    st.projects.add_role_message(pid, "⏸️ Deze taak vereist een mens of externe partij")

    rij = noochie_memo.verzamel(st, dd)["projecten"]["inhoud"][0]
    assert rij["titel"] == "village.nooch.earth is mobile friendly" and rij["status"] == "blocked"
    assert rij["comments_van_mensen"] == ["eerst kijken of de header op een telefoon past"]
    assert any("Deze taak vereist een mens" in r for r in rij["log"])
    plan = rij["uitvoerplan"]
    assert plan[0]["klaar"] and plan[0]["skill"] == "haal_pagina" and "93 tekens" in plan[0]["leeg"]
    assert not plan[1]["klaar"] and plan[1]["mens_taak"] and "geen skill" in plan[1]["waarom_niet"]
    assert rij["blokkeert_op"] == ["Voer een technische audit uit van CSS/HTML-broncode"]
    assert "creator_of_shoes" in rij["wacht_op"]


def test_haar_eigen_oude_ruis_gaat_eruit(tmp_path):
    """De gesloopte matchlaag liet op honderden projecten '@Rol, dit lijkt binnen jouw scope
    (skill: x). Oppakken?' achter, van `noochie_persona`. Dat leest ze niet terug als inhoud."""
    dd, st = _st(tmp_path)
    pid = _project(st, "Header design afgerond")
    st.projects.add_feed_entry(pid, "@Library, dit lijkt binnen jouw scope (skill: keyword_review). Oppakken?",
                               kind="comment", author_type="persona", author_id="noochie_persona")
    st.projects.add_feed_entry(pid, "de header staat nu, review graag", kind="comment",
                               author_type="human", author_id="stefan@nooch.earth")
    st.projects.add_feed_entry(pid, "✅ Mens-taak afgerond: Received company information",
                               kind="system", author_type="human", author_id="stefan@nooch.earth")
    rij = noochie_memo.verzamel(st, dd)["projecten"]["inhoud"][0]
    alles = json.dumps(rij, ensure_ascii=False)
    assert "dit lijkt binnen jouw scope" not in alles
    assert rij["comments_van_mensen"] == ["de header staat nu, review graag"]
    assert any(r.startswith("[mens] ✅ Mens-taak afgerond") for r in rij["log"])


def test_net_afgeronde_projecten_tellen_mee_en_future_niet(tmp_path):
    """Cristian/Apolo (done: disqualified) zegt iets over de leverancierszoektocht die nog loopt;
    de 58 future-projecten zijn per definitie nog niet aan de orde en tellen alleen."""
    dd, st = _st(tmp_path)
    klaar = _project(st, "Cristian from Apolo qualified as a sourcing partner", status="done")
    toekomst = st.projects.create(ROL, "Ooit een winkel in Alicante", "human", status="queued")
    st.projects.to_future(toekomst)
    pr = noochie_memo.verzamel(st, dd)["projecten"]
    titels = [r["titel"] for r in pr["inhoud"]]
    assert "Cristian from Apolo qualified as a sourcing partner" in titels
    assert "Ooit een winkel in Alicante" not in titels
    assert pr["per_status"].get("future") == 1
    assert next(r for r in pr["inhoud"] if r["titel"].startswith("Cristian"))["uitkomst"] == "approved after review"
    assert klaar


def test_pdf_bijlage_wordt_gelezen_binnen_budget(tmp_path):
    """De Mees Productions-pdf's en de top10-fabrieken-pdf zijn inhoud; via dezelfde lezer als de
    kennisbank, begrensd per bijlage en over de hele memo."""
    dd, st = _st(tmp_path)
    pid = _project(st, "Mees Productions als Portugal-partner beoordeeld", status="blocked")
    os.makedirs(os.path.join(dd, "attachments", pid), exist_ok=True)
    tekst = "Mees Productions sampling process: full service from development to production. " * 6
    with open(os.path.join(dd, "attachments", pid, "mees.pdf"), "wb") as f:
        f.write(_mini_pdf(tekst))
    st.projects.attach_file(pid, "MEES - Sampling process.pdf", f"attachments/{pid}/mees.pdf")
    st.projects.attach_add(pid, url="https://www.inescop.es/es/", title="INESCOP testlab")
    with mock.patch.object(noochie_memo, "PDF_TEKENS", 120):
        rij = noochie_memo.verzamel(st, dd)["projecten"]["inhoud"][0]
    soorten = {b["soort"]: b for b in rij["bijlagen"]}
    assert soorten["link"]["url"] == "https://www.inescop.es/es/"
    assert soorten["file"]["tekst"].startswith("Mees Productions sampling process")
    assert len(soorten["file"]["tekst"]) <= 120


def test_pdf_zonder_tekstlaag_wordt_benoemd_niet_verzonnen(tmp_path):
    dd, st = _st(tmp_path)
    pid = _project(st, "Tongue label Batch 4 gereed", status="running")
    os.makedirs(os.path.join(dd, "attachments", pid), exist_ok=True)
    with open(os.path.join(dd, "attachments", pid, "scan.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 dit is geen pdf")
    st.projects.attach_file(pid, "scan.pdf", f"attachments/{pid}/scan.pdf")
    rij = noochie_memo.verzamel(st, dd)["projecten"]["inhoud"][0]
    assert rij["bijlagen"][0]["tekst"] is None


def test_budget_houdt_de_invoer_begrensd(tmp_path):
    """Boven het budget krijgt een project alleen titel + status; wat vastzit gaat vóór wat loopt."""
    dd, st = _st(tmp_path)
    for i in range(6):
        _project(st, f"Lopend project {i}", status="running")
    vast = _project(st, "Vastgelopen project", status="blocked")
    st.projects.add_comment(vast, "x" * 400)
    with mock.patch.object(noochie_memo, "INVOER_BUDGET", 900):
        pr = noochie_memo.verzamel(st, dd)["projecten"]
    assert pr["inhoud"][0]["titel"] == "Vastgelopen project"
    assert pr["buiten_budget_alleen_titel"], "de rest hoort als titel-only te reizen"
    assert all(set(r) == {"titel", "status"} for r in pr["buiten_budget_alleen_titel"])
    assert len(pr["inhoud"]) + len(pr["buiten_budget_alleen_titel"]) == 7


def test_wiki_paginas_met_feiten(tmp_path):
    from nooch_village import wiki
    dd, st = _st(tmp_path)
    a = st.att.add(ROL, wiki.PAGINA_KIND, title="Materialen", body="LOVR is een appelleer-alternatief.",
                   meta={"feiten": [wiki.maak_feit("LOVR bevat geen PU", soort="materiaal")]})
    w = noochie_memo.verzamel(st, dd)["wiki"]
    assert w and w[0]["titel"] == "Materialen" and w[0]["eigenaar"] == ROL
    assert w[0]["feiten"] == ["LOVR bevat geen PU"] and a


# ── fail-closed ──────────────────────────────────────────────────────────────

def test_zonder_llm_geen_memo_en_niets_bezorgd(tmp_path):
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=None):
        r = noochie_memo.memo(st, dd, apply=True)
    assert r["ok"] is False and r["tekst"] is None and r["bezorgd"] is False
    assert "geen LLM-antwoord" in r["reden"]
    assert _founder_items(dd) == []


def test_dry_run_schrijft_wel_maar_bezorgt_niet(tmp_path):
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=MEMO):
        r = noochie_memo.memo(st, dd, apply=False)
    assert r["ok"] and r["tekst"].endswith(MEMO.split("\n", 1)[1].strip()) and r["bezorgd"] is False
    assert _founder_items(dd) == []


# ── de onderwerpregel ────────────────────────────────────────────────────────

def test_de_eerste_regel_is_de_preview_in_de_inbox():
    """De store leidt de preview af uit de tekst (één waarheid); de enige plek voor een leesbare
    lijstregel is dus vooraan in de tekst."""
    t = noochie_memo.met_onderwerp(MEMO, "2026-09-11")
    assert t.startswith("Memo van Noochie, 11 sep 2026: Mobiel · Leveranciers in Spanje\n\n### Mobiel")
    # 'Onderwerp:' of vet eromheen wordt niet dubbel
    t2 = noochie_memo.met_onderwerp("**Onderwerp: Claims**\n\n### Claims\ntekst", "2026-09-11")
    assert t2.startswith("Memo van Noochie, 11 sep 2026: Claims\n\n### Claims")
    # geen onderwerpregel geschreven → de koppen zelf
    t3 = noochie_memo.met_onderwerp("### A\nx\n### B\ny", "2026-09-11")
    assert t3.startswith("Memo van Noochie, 11 sep 2026: A · B\n\n### A")


# ── bezorgen ─────────────────────────────────────────────────────────────────

def test_de_memo_landt_bij_de_founder_van_noochie_en_ongewijzigd(tmp_path):
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=MEMO):
        r = noochie_memo.memo(st, dd, apply=True)
    assert r["ok"] and r["bezorgd"]
    items = _founder_items(dd)
    assert len(items) == 1
    it = items[0]
    assert it["by"] == noochie_memo.AFZENDER
    assert it["tekst"] == r["tekst"], "de herschrijf-poort heeft de memo aangeraakt"
    assert "python -m pytest tests/" in it["tekst"], "het commando hoort in de opgeslagen tekst te blijven"
    assert it.get("type") == noochie_memo.TYPE
    assert it["snippet"].startswith("Memo van Noochie, ") and "Mobiel · Leveranciers" in it["snippet"]


def test_precies_een_llm_call_op_de_hoog_inzet_site(tmp_path):
    """De herschrijf-poort in `NotifStore.add` zou een TWEEDE call doen (escalation_route) als het
    item zonder type binnenkwam. Eén call, en het is de onze."""
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=MEMO) as m:
        noochie_memo.memo(st, dd, apply=True)
    sites = [c.kwargs.get("call_site") for c in m.call_args_list]
    assert sites == [noochie_memo.CALL_SITE], sites


def test_de_memo_site_is_hoog_inzet():
    from nooch_village.llm_keuze import HOOG_INZET, ladder_voor
    assert noochie_memo.CALL_SITE in HOOG_INZET
    ladder = ladder_voor(noochie_memo.CALL_SITE) or ""
    assert ladder.startswith("anthropic:claude-sonnet"), ladder


def test_notify_founder_zonder_extra_blijft_identiek(tmp_path):
    """De elf bestaande aanroepers geven geen `extra` mee; voor hen mag niets veranderen —
    inclusief dat hun item wél langs de poort gaat (die typeert een rauwe signalering)."""
    from nooch_village.human_inbox import _notify_founder
    dd, st = _st(tmp_path)
    inbox = f"{dd}/human_inbox.json"
    with mock.patch("nooch_village.notifications._door_de_poort", return_value={}) as poort:
        _notify_founder(inbox, by="dorp", snippet="rauwe signalering")
        assert poort.called, "zonder type hoort een item langs de poort te gaan"
        poort.reset_mock()
        _notify_founder(inbox, by="noochie", snippet=MEMO, extra={"type": noochie_memo.TYPE})
        assert not poort.called, "met een type hoort een item de poort over te slaan"


def test_projecttitels_komen_uit_scope_zoals_op_het_bord(tmp_path):
    """Mijn eerste versie las `title`; op de echte data gaf dat zestien lege titels. De kaarttitel
    is `scope`, en `_scope_text` is de ene plek die dat afleidt — hier dus ook."""
    dd, st = _st(tmp_path)
    _project(st, "Website Re-Design Done")
    _project(st, "Black and White 269 samples made", status="blocked")
    pr = noochie_memo.verzamel(cockpit2._Stores(dd), dd)["projecten"]
    per = {r["titel"]: r for r in pr["inhoud"]}
    assert per["Website Re-Design Done"]["status"] == "running"
    assert "creator_of_shoes" in per["Black and White 269 samples made"]["wacht_op"]


# ── lezen in de inbox ────────────────────────────────────────────────────────

def test_de_inbox_toont_de_memo_als_document_met_codeblok(tmp_path):
    """Een memo is geen spanning: geen founder-kaart, wél markdown met een <pre> voor de opdracht,
    en de commando-swap (`_leesbaar`) blijft eraf — het commando is de bedoeling."""
    from nooch_village.views import inbox as vi
    dd, st = _st(tmp_path)
    with mock.patch("nooch_village.llm.reason", return_value=MEMO):
        noochie_memo.memo(st, dd, apply=True)
    n = _founder_items(dd)[0]
    assert vi._type_van(n) == "memo"
    kaart = vi._kaart_html(st, n)
    assert "memo van Noochie" in kaart and "<pre>" in kaart
    assert "python -m pytest tests/" in kaart, "de opdracht om te plakken hoort letterlijk op het scherm"
    assert "werpt dit op" not in kaart
    html = vi.render_verwerk(st, n, csrf_token="t")
    assert "<pre>" in html and "Gelezen?" in html
    rij = vi._inbox_row(st, n, "t")
    assert "Memo van Noochie" in rij and ">memo<" in rij
    # In de lijst: een eigen kop bovenaan, niet "Not yet through the gate".
    lijst = vi._poort_secties(st, _founder_items(dd), "t", "")
    assert "Memo's van Noochie" in lijst and "Not yet through the gate" not in lijst


def test_het_commando_alarm_slaat_een_memo_over():
    """Het alarm kijkt bij een memo niet eens naar de tekst; bij elk ander item wel."""
    from nooch_village import notifications as nf
    with mock.patch.object(nf, "volledig", return_value="draai python -m nooch_village.village once") as v:
        nf._meld_commando({"id": "x", "type": "memo"})
        assert not v.called
        nf._meld_commando({"id": "y"})
        assert v.called


def test_inbox_en_memo_delen_het_type():
    from nooch_village.views import inbox as vi
    assert vi._MEMO == noochie_memo.TYPE


def test_md_doc_codeblok_binnen_document():
    """Een codefence BINNEN een document wordt een <pre> waarin niets wordt opgemaakt; een fence om
    het hele document heen wordt nog steeds gestript."""
    from nooch_village.cockpit2_util import _md_doc
    html = _md_doc("Kop\n```\n- geen lijst\n**geen vet** <b>x</b>\n```\nna")
    assert "<pre>- geen lijst\n**geen vet** &lt;b&gt;x&lt;/b&gt;</pre>" in html
    assert "<p>Kop</p>" in html and "<p>na</p>" in html
    assert _md_doc("```\n## Kop\ntekst\n```") == "<h4>Kop</h4><p>tekst</p>"
