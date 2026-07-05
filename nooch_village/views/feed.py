"""Feed-functies (activiteiten-stroom, mentions, emoji-reacties) — brok 2 van de cockpit2-split."""
from __future__ import annotations

from nooch_village.web_base import _e
from nooch_village.cockpit2_util import _stamp, _md, _avatar, _name, _ICON_ADD_EMOJI, _person_name

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
    """(lijst voor de JS-autocomplete, naam→doel-map voor het parsen). Rollen + mensen."""
    js, by_name = [], {}
    for r in st.records.all():
        if getattr(r, "archived", False):
            continue
        nm = _name(r)
        js.append({"l": nm}); by_name[nm.lower()] = ("role", r.id)
    for pr in st.people.all():
        js.append({"l": pr.name}); by_name[pr.name.lower()] = ("person", pr.id)
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


def _feed_entry_html(st, entry: dict, role_name: str = "",
                     pid: str = "", csrf_token: str = "", mention_names=()) -> str:
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
                 f"<textarea name='text' rows='2'>{_e(entry.get('text', ''))}</textarea>"
                 f"<button class='btn ok sm' type='submit' name='action' value='feed_edit' "
                 f"style='margin-top:.3rem'>Opslaan</button></form></details>")
        deld = (f"<form method='post' action='/action' style='display:inline'>{hidf}"
                f"<button class='flink' type='submit' name='action' value='feed_remove' "
                f"onclick=\"return confirm('Comment verwijderen?')\">Verwijderen</button></form>")
        tools = f"<span class='fsep'>·</span>{editd}<span class='fsep'>·</span>{deld}"
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
