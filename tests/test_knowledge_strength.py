"""Kennislaag brok 2: berekende sterkte (puur uit het web) + gaten + betwist.
Soort verandert nooit; sterkte evolueert en kan nooit verouderen (komt tegenspraak erbij → betwist)."""
from __future__ import annotations

from nooch_village.insight import Insight, ClaimKind, EvidenceType
from nooch_village.knowledge import strength, is_verified, gaps, contested, Strength


def _bev(id, src, et=EvidenceType.MEASURED, supports=None):
    return Insight(id=id, claim=f"bevinding {id}", source=src, kind=ClaimKind.BEVINDING,
                   evidence_type=et, supports=supports or [])


def test_onbeslist_zonder_bewijs():
    s = Insight(id="s", claim="onze schoen is afbreekbaar", source="nooch", kind=ClaimKind.STANDPUNT)
    assert strength(s, [s]) == Strength.ONBESLIST
    assert is_verified(s, [s]) is False


def test_standpunt_erft_sterkte_van_onafhankelijke_gemeten_bevindingen():
    s = Insight(id="s", claim="schoen composteert", source="nooch", kind=ClaimKind.STANDPUNT)
    b1 = _bev("b1", "Lab A", supports=["s"])
    b2 = _bev("b2", "Lab B", supports=["s"])
    alln = [s, b1, b2]
    assert strength(s, alln) == Strength.GEVERIFIEERD     # 2 onafhankelijke + gemeten
    assert is_verified(s, alln) is True


def test_onafhankelijkheid_zelfde_bron_telt_als_een():
    s = Insight(id="s", claim="x", source="nooch", kind=ClaimKind.STANDPUNT)
    b1 = _bev("b1", "Lenzing PDF", supports=["s"])
    b2 = _bev("b2", "Lenzing PDF", supports=["s"])   # zelfde bron → 1 leg
    assert strength(s, [s, b1, b2]) == Strength.ONDERSTEUND


def test_bevestigd_zonder_gemeten():
    s = Insight(id="s", claim="x", source="nooch", kind=ClaimKind.STANDPUNT)
    b1 = _bev("b1", "Blog A", et=EvidenceType.REPORTED, supports=["s"])
    b2 = _bev("b2", "Blog B", et=EvidenceType.REPORTED, supports=["s"])
    assert strength(s, [s, b1, b2]) == Strength.BEVESTIGD     # 2 onafhankelijk, geen gemeten


def test_tegenspraak_overrulet_alles():
    s = Insight(id="s", claim="x", source="nooch", kind=ClaimKind.STANDPUNT)
    b1 = _bev("b1", "Lab A", supports=["s"])
    b2 = _bev("b2", "Lab B", supports=["s"])
    tegen = Insight(id="t", claim="juist niet", source="Lab C", kind=ClaimKind.BEVINDING,
                    evidence_type=EvidenceType.MEASURED, contradicts=["s"])
    assert strength(s, [s, b1, b2, tegen]) == Strength.BETWIST
    assert contested([s, b1, b2, tegen]) == [s]


def test_bevinding_telt_eigen_gemeten_bron_als_leg():
    b = _bev("b", "Lab A")                     # gemeten, eigen bron = 1 leg
    assert strength(b, [b]) == Strength.ONDERSTEUND
    b2 = _bev("b2", "Lab B", supports=["b"])   # tweede onafhankelijke gemeten leg
    assert strength(b, [b, b2]) == Strength.GEVERIFIEERD


def test_gaps_signaal_en_standpunt_zonder_bevinding():
    sig = Insight(id="sig", claim="zoekvolume stijgt", source="trends", kind=ClaimKind.SIGNAAL)
    st = Insight(id="st", claim="wij claimen X", source="nooch", kind=ClaimKind.STANDPUNT)
    st_ok = Insight(id="st2", claim="wij claimen Y", source="nooch", kind=ClaimKind.STANDPUNT)
    b = _bev("b", "Lab A", supports=["st2"])
    g = gaps([sig, st, st_ok, b])
    assert sig in g["signaal_zonder_bevinding"]
    assert st in g["standpunt_zonder_bevinding"]
    assert st_ok not in g["standpunt_zonder_bevinding"]   # heeft bewijs → geen gat
