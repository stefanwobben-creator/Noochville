"""Feed-functies (activiteiten-stroom, mentions, emoji-reacties) — brok 2 van de cockpit2-split."""
from __future__ import annotations

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import _stamp, _md, _avatar, _name, _ICON_ADD_EMOJI, _person_name, md_editor
from nooch_village import org

# Gecureerde set standaard emoji's met zoekwoorden (NL/EN) voor de picker.
_EMOJIS_FULL = [
    ("👍", "duim like goed prima"), ("👎", "duim slecht nee"), ("🙏", "dank bedankt please"),
    ("👏", "applaus klap"), ("🙌", "hoera yes"), ("💪", "sterk kracht power"), ("🤝", "deal akkoord hand"),
    ("😀", "blij lach happy"), ("😂", "lachen lol"), ("😉", "knipoog wink"), ("😍", "liefde hart love"),
    ("😎", "cool stoer"), ("🤔", "denken hmm"), ("😮", "wow verbaasd"), ("😢", "verdrietig sad"),
    ("😡", "boos angry"), ("🥳", "feest party"), ("😴", "slaap moe"),
    ("❤️", "hart liefde love rood"), ("💚", "hart groen"), ("💙", "hart blauw"),
    ("🔥", "vuur top fire"), ("⭐", "ster top star"), ("✨", "sprankel magie"),
    ("🎉", "feest party hoera"), ("🎊", "confetti"), ("✅", "check klaar done ok"), ("❌", "kruis fout nee"),
    ("⚠️", "waarschuwing let op warning"), ("❓", "vraag question"), ("❗", "uitroep belangrijk"),
    ("💡", "idee lamp insight"), ("🚀", "raket snel launch"), ("📈", "omhoog groei up"),
    ("📉", "omlaag daling down"), ("💰", "geld money"), ("⏰", "tijd klok deadline"), ("📌", "pin belangrijk"),
    ("🌱", "groei plant duurzaam"), ("🌍", "aarde wereld earth"), ("♻️", "recycle duurzaam"),
    ("👀", "kijk ogen"), ("🤖", "ai robot"), ("🙂", "glimlach"),
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
        nm = _person_name(st, aid) or "Iemand"
        return _avatar(nm, False), nm
    if atype == "persona":
        pa = st.personas.get(aid)
        nm = pa.name if pa else "AI"
        return _avatar(nm, True), nm
    if atype == "role":
        r = st.records.get(aid)
        return "<span class='av role'>R</span>", (_name(r) if r else "Rol")
    return "<span class='av'>🙋</span>", "Jij"


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
    pj_opts = "<option value=''>— kies project —</option>"
    for rid in sorted(by_role, key=lambda x: (_name(st.records.get(x)) if st.records.get(x) else str(x)).lower()):
        rn = _name(st.records.get(rid)) if st.records.get(rid) else str(rid)
        opts = "".join(f"<option value='{_e(pp['id'])}'>{_e(str(pp.get('scope') or pp['id'])[:60])}</option>"
                       for pp in by_role[rid])
        pj_opts += f"<optgroup label='{_e(rn)}'>{opts}</optgroup>"
    return role_opts, pj_opts


def _wall_outcome_form(pid: str, eid: str, csrf: str, prefill: str, role_opts: str, pj_opts: str) -> str:
    """Discrete '→ uitkomst'-actie bij een wall-comment: route 'm naar één van de vijf bestaande
    uitkomsten. Progressive disclosure per type (mirror van het werkoverleg oc_details). De inhoud is
    bewerkbaar en voorgevuld met de comment-tekst (voor project/action kort je 'm typisch in tot een
    titel; voor note/info blijft de volle tekst logisch). De toelichting is verplicht (rationale)."""
    hid = (f"<input type='hidden' name='csrf' value='{_e(csrf)}'>"
           f"<input type='hidden' name='pid' value='{_e(pid)}'>"
           f"<input type='hidden' name='item' value='{_e(eid)}'>")

    def oc(otype: str, summary: str, target_field: str) -> str:
        return (f"<details class='wo-ocd box-details'><summary>{summary}</summary>"
                f"<form method='post' action='/action' class='wo-oc'>{hid}"
                f"<input type='hidden' name='otype' value='{otype}'>"
                f"<label class='att-lbl'>Inhoud (bewerkbaar)</label>"
                f"<textarea name='content' rows='2'>{_e(prefill)}</textarea>"
                f"{target_field}"
                f"<label class='att-lbl'>Toelichting (verplicht)</label>"
                f"<textarea name='toelichting' rows='2' required "
                f"placeholder='waarom deze uitkomst?'></textarea>"
                f"<button class='btn sm' type='submit' name='action' value='wall_outcome'>Vastleggen</button>"
                f"</form></details>")

    info = oc("info", "Info",
              "<span class='muted'>Gebruik @naam of @rol in de inhoud voor gericht; anders iedereen.</span>")
    proj = oc("project", "Project",
              f"<label class='att-lbl'>Op welke rol?</label><select name='owner'>{role_opts}</select>")
    act = oc("action", "Actie",
             f"<label class='att-lbl'>Aan welk project?</label><select name='pid_link'>{pj_opts}</select>")
    note = oc("note", "Note",
              f"<label class='att-lbl'>Note bij welke rol?</label><select name='note_role'>{role_opts}</select>")
    rov = oc("roloverleg", "Roloverleg",
             "<span class='muted'>Wordt een add_role-voorstel op de roloverleg-agenda (mens-route).</span>")
    return (f"<details class='fedit'><summary class='flink'>→ uitkomst</summary>"
            f"{info}{proj}{act}{note}{rov}</details>")


def _feed_entry_html(st, entry: dict, role_name: str = "",
                     pid: str = "", csrf_token: str = "", mention_names=(),
                     outcome_opts=None) -> str:
    kind, atype, aid = _feed_norm(entry)
    av, nm = _feed_who(st, atype, aid)
    if atype == "role":
        who = f"<b class='fname'>@{_e(nm)}</b>"
    elif atype in ("person", "persona") and role_name:
        who = f"<b class='fname'>{_e(nm)}</b> <span class='frole'>@{_e(role_name)}</span>"
    else:
        who = f"<b class='fname'>{_e(nm)}</b>"
    rx = "".join(f"<span class='chip outline'>{emo} {cnt}</span>" for emo, cnt in (entry.get("reactions") or {}).items())
    picker = ""
    eid = entry.get("id")
    if csrf_token and eid:
        btns = "".join(
            f"<form method='post' action='/action' class='emo-f' data-k='{_e(kw)}' style='display:inline'>"
            f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
            f"<input type='hidden' name='pid' value='{_e(pid)}'>"
            f"<input type='hidden' name='item' value='{_e(eid)}'>"
            f"<input type='hidden' name='emoji' value='{emo}'>"
            f"<button class='emo' type='submit' name='action' value='react_add' title='{_e(kw)}'>{emo}</button></form>"
            for emo, kw in _EMOJIS_FULL)
        picker = (f"<details class='emoji-pick'><summary class='emoji-add' title='reactie' "
                  f"aria-label='reactie toevoegen'>{_ICON_ADD_EMOJI}</summary>"
                  f"<div class='emoji-pop'>"
                  f"<input class='emo-search' type='text' placeholder='Zoek emoji…' oninput='emoFilter(this)'>"
                  f"<div class='emo-grid'>{btns}</div></div></details>")
    bubble = _md(entry.get("text", ""))
    if mention_names:
        bubble = _hilite_mentions(bubble, mention_names)
    # Eigen comment (mens) is wijzigbaar/verwijderbaar.
    tools = ""
    if csrf_token and eid and atype == "human":
        hidf = (f"<input type='hidden' name='csrf' value='{_e(csrf_token)}'>"
                f"<input type='hidden' name='pid' value='{_e(pid)}'>"
                f"<input type='hidden' name='item' value='{_e(eid)}'>")
        editd = (f"<details class='fedit'><summary class='flink'>Wijzigen</summary>"
                 f"<form method='post' action='/action' class='pf' style='margin-top:.3rem'>{hidf}"
                 f"{md_editor('text', entry.get('text', ''), rows=3, placeholder='Bewerk je reactie…')}"
                 f"<button class='btn ok sm' type='submit' name='action' value='feed_edit' "
                 f"style='margin-top:.3rem'>Opslaan</button></form></details>")
        deld = (f"<form method='post' action='/action' style='display:inline'>{hidf}"
                f"<button class='flink' type='submit' name='action' value='feed_remove' "
                f"onclick=\"return confirm('Comment verwijderen?')\">Verwijderen</button></form>")
        tools = f"<span class='fsep'>·</span>{editd}<span class='fsep'>·</span>{deld}"
    # → uitkomst: elke comment (mens én persona) mag de mens naar een uitkomst routeren; niet op
    # de neutrale system-audit-entry (die is zelf al de uitkomst-trail).
    if outcome_opts and csrf_token and eid and kind != "system":
        _ro, _po = outcome_opts
        oc = _wall_outcome_form(pid, eid, csrf_token, entry.get("text", ""), _ro, _po)
        tools += f"<span class='fsep'>·</span>{oc}"
    return (f"<div class='fentry'>"
            f"<div class='fhead'>{av}<span class='fwho'>{who}</span>"
            f"<span class='fstamp'>{_e(_stamp(entry.get('at')))}</span></div>"
            f"<div class='fbubble'>{bubble}</div>"
            f"<div class='ffoot'><div class='ffoot-l'>{rx}{picker}{tools}</div></div>"
            f"</div>")


def _feed_author_options(st, p: dict) -> str:
    """Namens-keuze voor de composer: jij (reactie) + de rolvervullers van de eigenaar-rol (update)."""
    opts = ["<option value='human:'>🙋 Jij (reactie)</option>"]
    orec = st.records.get(p.get("owner"))
    if orec is not None:
        for f in st.assign.fillers_of(orec.id, record=orec):
            if f.type == "person":
                opts.append(f"<option value='person:{_e(f.id)}'>{_e(_person_name(st, f.id))} (update)</option>")
            else:
                pa = st.personas.get(f.id)
                opts.append(f"<option value='persona:{_e(f.id)}'>🤖 {_e(pa.name if pa else f.id)} (update)</option>")
    return "".join(opts)
