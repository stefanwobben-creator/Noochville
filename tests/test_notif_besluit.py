"""Beslis direct (founder, 19 jul): op een spanning uit de inbox wil de mens gewoon ja,
nee of een suggestie zeggen. Borgingen: (1) een besluit landt als menselijke reactie op
de bron-feed (@rol) zodat de bewoner het zelf oppakt (worked=False), plus een notificatie
aan de eigenaar-rol, en de spanning sluit; (2) een suggestie zonder tekst wordt geweigerd;
(3) zonder bron-project geen besluit-route (fail-closed, de ping blijft daarvoor); (4) de
verwerk-wizard toont de volledige vraag uit de bron-feed-entry naast de 160-tekens-snippet."""
from __future__ import annotations

import types

from nooch_village.cockpit2 import _act_notif_besluit
from nooch_village.notifications import NotifStore
from nooch_village.projects import ProjectLedger
from nooch_village.views.inbox import _spanning_pane


def _ctx(tmp_path, **over):
    pj = ProjectLedger(f"{tmp_path}/projects.json")
    pid = pj.create("website_watcher", "Bezoekersdaling duiden", "human")
    entry = pj.add_feed_entry(
        pid, "@The Source — SPANNING: bezoekers 114→73. WAT IK NODIG HEB: kies A of B.",
        kind="comment", author_type="role", author_id="website_watcher")
    notif = NotifStore(f"{tmp_path}/notifications.json")
    n = notif.add("role", "the_source", pid, entry["id"], by="Walter Website",
                  snippet="bezoekers 114→73 — kies A of B")
    st = types.SimpleNamespace(
        notif=notif, projects=pj,
        records=types.SimpleNamespace(get=lambda rid: None),
        people=types.SimpleNamespace(by_email=lambda e: None))
    velden = {"nid": n["id"], "besluit": "ja", "toelichting": "", **over}
    c = types.SimpleNamespace(nxt="/inbox", st=st, g=lambda k: velden.get(k, ""),
                              pj=pj, username="stefan@nooch.earth")
    return c, st, pj, pid, n


def test_ja_landt_als_reactie_en_sluit_de_spanning(tmp_path):
    c, st, pj, pid, n = _ctx(tmp_path, besluit="ja", toelichting="ga voor optie B")
    _, msg = _act_notif_besluit(c)
    assert msg.startswith("✓ ✓ JA")
    p = pj.get(pid)
    laatste = p["log"][-1]
    assert laatste["author"]["type"] == "human"                # menselijke reactie...
    assert "✓ JA" in laatste["text"] and "optie B" in laatste["text"]
    assert laatste["text"].startswith("@website_watcher")      # ...gericht aan de rol
    assert p["worked"] is False                                 # de bewoner pakt het weer op
    rol_notifs = st.notif.for_targets([("role", "website_watcher")])
    assert rol_notifs and "✓ JA" in rol_notifs[0]["snippet"]    # en ziet het in zijn inbox
    assert st.notif.status_of(st.notif._find(n["id"])) == "verwerkt"   # beslissen ís verwerken


def test_suggestie_zonder_tekst_geweigerd(tmp_path):
    c, st, pj, pid, n = _ctx(tmp_path, besluit="suggestie", toelichting="")
    _, msg = _act_notif_besluit(c)
    assert msg.startswith("✗")
    assert st.notif.status_of(st.notif._find(n["id"])) != "verwerkt"


def test_zonder_bron_project_fail_closed(tmp_path):
    c, st, pj, pid, n = _ctx(tmp_path)
    st.notif._find(n["id"])["project_id"] = ""                 # spanning zonder bron
    _, msg = _act_notif_besluit(c)
    assert "geen bron-project" in msg


def test_wizard_toont_de_volledige_vraag(tmp_path):
    c, st, pj, pid, n = _ctx(tmp_path)
    st.notif.verwerkingen_of = lambda x: []                    # view-afhankelijkheid
    html = _spanning_pane(st, st.notif._find(n["id"]))
    assert "De volledige vraag" in html
    assert "WAT IK NODIG HEB" in html                          # de échte tekst, niet de snippet
