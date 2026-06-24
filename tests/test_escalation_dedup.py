"""Inbox-hygiëne: escalaties dedupliceren op INHOUD, niet op het toevallige voorstel-id.

De storm was zes kopieën van twee voorstellen (elke simulate-run een nieuw id). Eén
voorstel hoort één openstaande beslissing te zijn. Dedup geldt onder de pending-items:
een al beslist (afgewezen) voorstel dat opnieuw opduikt, mag de mens wél weer zien."""
from __future__ import annotations

from nooch_village.human_inbox import HumanInbox


def _proposal(pid, *, proposer="trends", kind="amend_role", role_id="trends",
              add_acc=None):
    return {
        "id": pid,
        "proposer_role": proposer,
        "change": {"kind": kind, "role_id": role_id,
                   "add_accountabilities": add_acc or ["dagelijkse Field Note schrijven"]},
        "tension": "x", "trigger_example": "y", "rationale": "z",
    }


def test_identiek_voorstel_ander_id_dedupt(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    id1 = hi.add_escalation(_proposal("p1"), gate="G2", reason="dup")
    id2 = hi.add_escalation(_proposal("p2"), gate="G2", reason="dup")   # ander id, zelfde inhoud
    assert id1 == id2                       # samengevallen
    assert len(hi.pending()) == 1


def test_zes_kopieen_worden_een(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    for i in range(6):
        hi.add_escalation(_proposal(f"p{i}"), gate="G2", reason="dup")
    assert len(hi.pending()) == 1


def test_verschillende_voorstellen_blijven_apart(tmp_path):
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    hi.add_escalation(_proposal("p1", proposer="trends", role_id="trends"),
                      gate="G2", reason="a")
    hi.add_escalation(_proposal("p2", proposer="website_watcher", role_id="website_watcher",
                                add_acc=["plastic producten goedkeuren voor promotie"]),
                      gate="G4", reason="b")
    assert len(hi.pending()) == 2           # echt twee verschillende beslissingen


def test_afgewezen_voorstel_mag_terugkomen(tmp_path):
    """Dedup geldt onder pending: een al afgewezen voorstel dat opnieuw opduikt
    levert wél een nieuw item (de mens beslist opnieuw)."""
    hi = HumanInbox(str(tmp_path / "inbox.json"))
    id1 = hi.add_escalation(_proposal("p1"), gate="G2", reason="dup")
    hi.resolve(id1, "rejected", reason="nee")
    id2 = hi.add_escalation(_proposal("p2"), gate="G2", reason="dup")   # identiek, maar p1 is beslist
    assert id2 != id1
    assert len(hi.pending()) == 1           # het nieuwe pending-item
