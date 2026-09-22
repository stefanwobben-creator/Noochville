"""Feed-functies (activiteiten-stroom, mentions, emoji-reacties) — brok 2 van de cockpit2-split."""
from __future__ import annotations

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import inline_edit, inline_edit_knop, _stamp, _md, _avatar, _name, _ICON_ADD_EMOJI, _person_name, md_editor
from nooch_village import org

# Gecureerde set standaard emoji's met zoekwoorden voor de picker.
_EMOJIS_FULL = [
    ("👍", "thumb like good fine"), ("👎", "thumb bad no"), ("🙏", "thanks please"),
    ("👏", "applause clap"), ("🙌", "hooray yes"), ("💪", "strong power"), ("🤝", "deal agreed hand"),
    ("😀", "glad smile happy"), ("😂", "laugh lol"), ("😉", "wink"), ("😍", "love heart"),
    ("😎", "cool"), ("🤔", "thinking hmm"), ("😮", "wow surprised"), ("😢", "sad"),
    ("😡", "angry"), ("🥳", "party celebrate"), ("😴", "sleep tired"),
    ("❤️", "heart love red"), ("💚", "heart green"), ("💙", "heart blue"),
    ("🔥", "fire top"), ("⭐", "star top"), ("✨", "sparkle magic"),
    ("🎉", "party hooray"), ("🎊", "confetti"), ("✅", "check done ok"), ("❌", "cross wrong no"),
    ("⚠️", "warning caution"), ("❓", "question"), ("❗", "exclamation important"),
    ("💡", "idea lamp insight"), ("🚀", "rocket fast launch"), ("📈", "up growth"),
    ("📉", "down decline"), ("💰", "money"), ("⏰", "time clock deadline"), ("📌", "pin important"),
    ("🌱", "growth plant sustainable"), ("🌍", "earth world"), ("♻️", "recycle sustainable"),
    ("👀", "look eyes"), ("🤖", "ai robot"), ("🙂", "smile"),
]


def _feed_norm(entry: dict):
    """Normaliseer een feed-entry naar (kind, author_type, author_id). Leest zowel het nieuwe
    schema (author/kind) als het oude ({who: 'mens'|'rol'})."""
    if "author" in entry:
        a = entry.get("author") or {}
        return entry.get("kind", "comment"), a.get("type", "human"), a.get("id", "")
    if entry.get("who") == "rol":
        return "update", "role", ""
    return "comment", "human", ""


def _feed_who(st, atype: str, aid: str):
    """(avatar-html, naam) voor een feed-auteur."""
    if atype == "person":
        nm = _person_name(st, aid) or "Someone"
        return _avatar(nm, False), nm
    if atype == "persona":
        pa = st.personas.get(aid)
        nm = pa.name if pa else "AI"
        return _avatar(nm, True), nm
    if atype == "role":
        r = st.records.get(aid)
        return "<span class='av role'>R</span>", (_name(r) if r else "Role")
    return "<span class='av'>🙋</span>", "You"


def _mentionables(st):
    """(lijst voor de JS-autocomplete, naam→doel-map voor het parsen). Rollen + AI-inwoners (persona-naam)
    + mensen. Een persona-naam wijst naar de rol die de persona vervult, zodat @rolnaam en @persona-naam
    exact hetzelfde doel (notificatie + reply) raken. Rolnamen winnen bij een naam-botsing (niet overschrijven)."""
    js, by_name = [], {}
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        nm = _name(r)
        js.append({"l": nm}); by_name.setdefault(nm.lower(), ("role", r.id))
    # persona-naam → de rol die 'm vervult (via de assignments-laag, zelfde bron als _owner_ai)
    role_by_persona = {}
    assign = getattr(st, "assign", None)
    if assign is not None:
        for r in st.records.all():
            if getattr(r, "archived", False):
                continue
            try:
                for f in assign.fillers_of(r.id, record=r):
                    if getattr(f, "type", None) == "persona":
                        role_by_persona.setdefault(f.id, r.id)
            except Exception:
                continue
    personas = getattr(st, "personas", None)
    for p in (personas.all() if personas else []):
        role_id = role_by_persona.get(p.id)
        if not role_id or not (p.name or "").strip():
            continue
        key = p.name.lower()
        if key in by_name:                          # rolnaam met dezelfde naam wint
            continue
        js.append({"l": p.name}); by_name[key] = ("role", role_id)
    for pr in st.people.all():
        js.append({"l": pr.name}); by_name.setdefault(pr.name.lower(), ("person", pr.id))
    return js, by_name


def _mentions_in(text: str, by_name: dict):
    """(type, id, naam) voor elke '@naam' uit by_name die in de tekst voorkomt."""
    t = (text or "").lower()
    return [(ty, i, nm) for nm, (ty, i) in by_name.items() if ("@" + nm) in t]


def _hilite_mentions(html: str, names) -> str:
    """Markeer '@naam' in al-gerenderde (veilige) HTML. Langste namen eerst (subset-botsing)."""
    for nm in sorted(names, key=len, reverse=True):
        esc = _e(nm)
        html = html.replace("@" + esc, f"<span class='ment'>@{esc}</span>")
    return html


def _wall_outcome_opts(st):
    """(role_opts, project_opts) voor het wall-outcome-formulier — één keer per wall berekenen
    (niet per comment). Rollen (geen cirkels, niet gearchiveerd) voor project-eigenaar + note-rol;
    projecten gegroepeerd per eigenaar-rol voor de actie-koppeling. De server-side gates blijven leidend."""
    roles = [r for r in st.records.all() if not org.is_circle(r) and not getattr(r, "archived", False)]
    role_opts = "".join(f"<option value='{_e(r.id)}'>{_e(_name(r))}</option>" for r in roles)
    by_role: dict = {}
    for pp in st.projects.all():
        if not pp.get("archived") and pp.get("owner"):
            by_role.setdefault(pp["owner"], []).append(pp)
    pj_opts = "<option value=''>— pick project —</option>"
    for rid in sorted(by_role, key=lambda x: (_name(st.records.get(x)) if st.records.get(x) else str(x)).lower()):
        rn = _name(st.records.get(rid)) if st.records.get(rid) else str(rid)
        opts = "".join(f"<option value='{_e(pp['id'])}'>{_e(str(pp.get('scope') or pp['id'])[:60])}</option>"
                       for pp in by_role[rid])
        pj_opts += f"<optgroup label='{_e(rn)}'>{opts}</optgroup>"
    return role_opts, pj_opts


def _wall_outcome_form(pid: str, eid: str, csrf: str, prefill: str, role_opts: str, pj_opts: str,
                       *, extra_hid: str = "", summary: str = "→ outcome") -> str:
    """Discrete '→ uitkomst'-actie bij een bron-comment: route 'm naar één van de bestaande
    uitkomsten. Progressive disclosure per type (mirror van het werkoverleg oc_details). De inhoud is
    bewerkbaar en voorgevuld met de comment-tekst (voor project/action kort je 'm typisch in tot een
    titel; voor note/info blijft de volle tekst logisch). Geen toelichting-veld: wil je context, vraag 'm
    aan de indiener.

    Herbruikbaar: `extra_hid` voegt extra verborgen velden toe aan elk formulier (de inbox geeft zo een
    `nid` + `next=/inbox` mee zodat dezelfde `wall_outcome`-handler het inbox-item op verwerkt zet).
    `summary` past de klik-label aan."""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='pid' value='{_e(pid)}'>"
           f"<input type='hidden' name='item' value='{_e(eid)}'>"
           f"{extra_hid}")

    def oc(otype: str, summary: str, target_field: str) -> str:
        return (f"<details class='wo-ocd box-details'><summary>{summary}</summary>"
                f"<form method='post' action='/action' class='wo-oc'>{hid}"
                f"<input type='hidden' name='otype' value='{otype}'>"
                f"<label class='att-lbl'>Content (editable)</label>"
                f"<textarea name='content' rows='2'>{_e(prefill)}</textarea>"
                f"{target_field}"
                f"<button class='btn sm' type='submit' name='action' value='wall_outcome'>Record</button>"
                f"</form></details>")

    # 'Info' is hier weg (29 aug 2026), samen met dezelfde keuze in de inbox en het werkoverleg.
    # Drie schermen, één verwerk-mechaniek, dus dezelfde uitkomsten — zie
    # tests/test_verwerk_uitkomsten_bevroren.py voor de meting en de grond.
    proj = oc("project", "Project",
              f"<label class='att-lbl'>On which role?</label><select name='owner'>{role_opts}</select>")
    act = oc("action", "Action",
             f"<label class='att-lbl'>To which project?</label><select name='pid_link'>{pj_opts}</select>")
    note = oc("note", "Note",
              f"<label class='att-lbl'>Note on which role?</label><select name='note_role'>{role_opts}</select>")
    rov = oc("roloverleg", "Governance meeting",
             "<span class='muted'>Becomes an add_role proposal on the governance-meeting agenda (human route).</span>")
    return (f"<details class='fedit'><summary class='flink'>{_e(summary)}</summary>"
            f"{proj}{act}{note}{rov}</details>")


def emoji_kiezer(knoppen: str, icoon: str = "", titel: str = "reaction") -> str:
    """De SCHIL van de emoji-kiezer: knop, popup, zoekveld, raster. Eén plek.

    WAAROM DIT EEN EIGEN FUNCTIE IS. De kiezer heeft twee gebruikers met hetzelfde uiterlijk en
    een andere actie: onder een bericht plaatst hij een REACTIE (een formulier per emoji), in de
    invoerbalk zet hij het teken in je TEKST (een knop per emoji, JS). Zou de tweede zijn eigen
    schil krijgen, dan is de emoji-lijst op het ene scherm na één wijziging langer dan op het
    andere — precies wat `reactie_blok` hieronder zelf al beschrijft.

    Wat de aanroeper levert is dus alleen de inhoud van het raster; de rest staat hier."""
    return (f"<details class='emoji-pick'><summary class='emoji-add' title='{_e(titel)}' "
            f"aria-label='{_e(titel)}'>{icoon or _ICON_ADD_EMOJI}</summary>"
            f"<div class='emoji-pop'>"
            f"<input class='emo-search' type='text' placeholder='Search emoji…' data-emo-zoek>"
            f"<div class='emo-grid'>{knoppen}</div></div></details>")


def emoji_invoeg_knoppen(doel: str) -> str:
    """De emoji's als INVOEGKNOPPEN voor een tekstveld, met dezelfde lijst en dezelfde klassen
    als de reactie-variant. `doel` is de id van het veld waar het teken in belandt.

    `type='button'`, en dat is geen detail: deze knoppen staan in de invoerbalk náást het
    schrijfformulier, en een knop zonder type is een submit."""
    return "".join(
        f"<button type='button' class='emo' data-emo-invoeg='{_e(doel)}' "
        f"data-k='{_e(kw)}' title='{_e(kw)}'>{emo}</button>"
        for emo, kw in _EMOJIS_FULL)


def reactie_blok(entry: dict, csrf_token: str, velden: dict) -> tuple[str, str]:
    """De emoji-reacties van één bericht: (de tellers, de kiezer). Gedeeld door de projectfeed en
    de kanalen in Messages.

    DIT STOND INLINE IN `_feed_entry_html`, en Messages had helemaal niets. Het er een tweede keer
    uitschrijven zou precies de fout zijn die `docs/CONVENTIES.md` verbiedt: twee vormen van
    hetzelfde die na één wijziging uit de pas lopen — en dan is de emoji-lijst op het ene scherm
    langer dan op het andere zonder dat iemand het merkt.

    `velden` is wat de POST moet dragen om het bericht terug te vinden: `{"pid": …}` voor een
    projectfeed, `{"kanaal": …}` voor een kanaal. Eén actie (`react_add`), twee adressen.

    Geen id op het bericht = geen reacties. Dat is het oude schema; fail-closed, geen knop die
    straks niets raakt."""
    rx = "".join(f"<span class='chip outline'>{emo} {cnt}</span>"
                 for emo, cnt in (entry.get("reactions") or {}).items())
    eid = entry.get("id")
    if not (csrf_token and eid):
        return rx, ""
    verborgen = "".join(f"<input type='hidden' name='{_e(k)}' value='{_e(v)}'>"
                        for k, v in velden.items())
    btns = "".join(
        f"<form method='post' action='/action' class='emo-f' data-k='{_e(kw)}' style='display:inline'>"
        f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
        f"{verborgen}"
        f"<input type='hidden' name='item' value='{_e(eid)}'>"
        f"<input type='hidden' name='emoji' value='{emo}'>"
        f"<button class='emo' type='submit' name='action' value='react_add' title='{_e(kw)}'>{emo}</button></form>"
        for emo, kw in _EMOJIS_FULL)
    return rx, emoji_kiezer(btns)


def _feed_entry_html(st, entry: dict, role_name: str = "",
                     pid: str = "", csrf_token: str = "", mention_names=(),
                     outcome_opts=None, terug: str = "") -> str:
    """`terug` is de plek waar de bewerk-acties naartoe redirecten. Zonder die waarde valt de
    dispatch terug op "/" en belandt de mens na het opslaan van een comment op het beginscherm —
    weg uit het project waarin hij aan het werk was."""
    kind, atype, aid = _feed_norm(entry)
    av, nm = _feed_who(st, atype, aid)
    if atype == "role":
        who = f"<b class='fname'>@{_e(nm)}</b>"
    elif atype in ("person", "persona") and role_name:
        who = f"<b class='fname'>{_e(nm)}</b> <span class='frole'>@{_e(role_name)}</span>"
    else:
        who = f"<b class='fname'>{_e(nm)}</b>"
    eid = entry.get("id")
    rx, picker = reactie_blok(entry, csrf_token, {"pid": pid})
    bubble = _md(entry.get("text", ""))
    if mention_names:
        bubble = _hilite_mentions(bubble, mention_names)
    if csrf_token and eid and atype == "human":
        # HETZELFDE COMPONENT als "Edit before confirming" op /rapport — zie
        # cockpit2_util.inline_edit. `terug` gaat mee zodat opslaan je op de projectkaart houdt.
        _hid2 = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                 f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                 f"<input type='hidden' name='item' value='{_e(eid)}'>"
                 f"<input type='hidden' name='next' value='{_e(terug)}'>")
        bubble = inline_edit(
            bubble,
            md_editor("text", entry.get("text", ""), rows=3, placeholder="Edit your reply…"),
            sleutel=eid, opslaan="feed_edit", verborgen=_hid2, toon_cls="fbody")
    # Eigen comment (mens) is wijzigbaar/verwijderbaar.
    tools = ""
    if csrf_token and eid and atype == "human":
        hidf = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='item' value='{_e(eid)}'>")
        # INLINE BEWERKEN, zoals de projecttitel het al doet: het veld staat op de plek van de
        # tekst zelf, niet als tweede veld eronder. Een <details> dat een kopie van de bubbel
        # opent, laat je twee versies van dezelfde regel naast elkaar lezen en je moet raden welke
        # de echte is. De bubbel-kant staat in `_bubble_of_editor` hieronder.
        editd = ""
        deld = (f"<form method='post' action='/action' class='fentry-inline'>{hidf}"
                f"<button class='flink' type='submit' name='action' value='feed_remove' "
                f"onclick=\"return confirm('Remove comment?')\">Remove</button></form>")
        tools = (f"<span class='fsep'>·</span>"
                 f"{inline_edit_knop()}"
                 f"<span class='fsep'>·</span>{deld}")
    # → uitkomst: elke comment (mens én persona) mag de mens naar een uitkomst routeren; niet op
    # de neutrale system-audit-entry (die is zelf al de uitkomst-trail).
    # DE "→ outcome"-KIEZER IS WEG. Hij stond onder elk bericht en werd niet gebruikt: routeren
    # gebeurt in de praktijk vanuit de inbox of via een @mention, niet vanaf een losse comment. Een
    # affordance die niemand gebruikt is geen neutrale toevoeging — hij staat onder élk bericht en
    # maakt de wall drukker naarmate er meer gesprek is.
    #
    # `_wall_outcome_form` en `_wall_outcome_opts` blijven bestaan: de checklist-kant gebruikt ze
    # nog (views/checklists.py) en de `wall_outcome`-dispatch bedient de inbox-route.
    # KEEP IN WIKI (fase 7). Eén regel uit dit gesprek als FEIT op een wiki-pagina, met herkomst.
    # De opslag bestond al (`meta["feiten"]`, zie wiki.py); dit is alleen de ingang, zoals het
    # prototype hem toont: een knop per bericht die een keuzelijst van pagina's uitklapt.
    #
    # Niet op de system-entry: die IS al de audit-trail van het project, en een feit dat zegt
    # "moved from Active to Waiting" hoort niet in een wiki. Alleen op wat een mens schreef.
    keep = _keep_in_wiki_form(st, pid, entry, csrf_token, terug) if (csrf_token and eid and atype != "system") else ""
    return (f"<div class='fentry editor-inline'>"
            f"<div class='fhead'>{av}<span class='fwho'>{who}</span>"
            f"<span class='fstamp'>{_e(_stamp(entry.get('at')))}</span></div>"
            f"<div class='fbubble'>{bubble}</div>"
            f"<div class='ffoot'><div class='ffoot-l'>{rx}{picker}{tools}{keep}</div></div>"
            f"</div>")


def _keep_wiki_opties(st) -> str:
    """De pagina's waar een feit heen kan: elke wiki-pagina (kind="note") van het dorp.

    Geen rol-grens: je houdt een feit bij het ONDERWERP (de leverancier, het materiaal), en dat
    onderwerp staat zelden op de rol waar het gesprek toevallig plaatsvond. Dezelfde redenering
    als bij `[[links]]`, die ook geen rolgrens kennen."""
    from nooch_village import wiki
    uit = []
    for a in st.att.by_kind(wiki.PAGINA_KIND):
        uit.append(f"<option value='{_e(a.id)}'>{_e(a.title or a.id)}</option>")
    return "".join(uit)


def _keep_in_wiki_form(st, pid: str, entry: dict, csrf_token: str, terug: str) -> str:
    """De 'Keep in wiki'-uitklapper onder één bericht."""
    opties = _keep_wiki_opties(st)
    if not opties:
        return ""                     # geen enkele pagina → geen knop die nergens heen kan
    eid = str(entry.get("id") or "")
    return (f"<span class='fsep'>·</span>"
            f"<details class='fentry-keep'><summary class='flink'>Keep in wiki</summary>"
            f"<form method='post' action='/action' class='qadd-form'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='pid' value='{_e(pid)}'>"
            f"<input type='hidden' name='item' value='{_e(eid)}'>"
            f"<input type='hidden' name='next' value='{_e(terug)}'>"
            f"<label class='att-lbl' for='kw-{_e(eid)}'>Keep as a fact on which page?</label>"
            f"<select id='kw-{_e(eid)}' name='aid'>{opties}</select>"
            f"<p class='muted'>Added under <b>Facts</b>, with this project and this message as its "
            f"source.</p>"
            f"<div class='qadd-row'><button class='btn ok sm' type='submit' name='action' "
            f"value='keep_in_wiki'>Keep</button></div></form></details>")


def _feed_author_options(st, p: dict) -> str:
    """Namens-keuze voor de composer: jij (reactie) + de rolvervullers van de eigenaar-rol (update)."""
    opts = ["<option value='human:'>🙋 You (reply)</option>"]
    orec = st.records.get(p.get("owner"))
    if orec is not None:
        for f in st.assign.fillers_of(orec.id, record=orec):
            if f.type == "person":
                opts.append(f"<option value='person:{_e(f.id)}'>{_e(_person_name(st, f.id))} (update)</option>")
            else:
                pa = st.personas.get(f.id)
                opts.append(f"<option value='persona:{_e(f.id)}'>🤖 {_e(pa.name if pa else f.id)} (update)</option>")
    return "".join(opts)
