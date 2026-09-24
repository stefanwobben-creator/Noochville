"""Het indelingsrapport van de wiki, en de handvol pagina's die met de hand geplaatst zijn.

WAT DIT WEL EN NIET IS. Het bakje van een pagina wordt AFGELEID (zie `domeinen.bakje_van`) en
nergens opgeslagen — er valt dus niets te backfillen. Wat hier staat is twee dingen:

  1. een RAPPORT: waar landt elke pagina, en via welke stap van de regel. Dat is de manier om te
     zien of de indeling nog klopt zonder ergens een tweede telling bij te houden.
  2. een WERKLIJST: de pagina's die in Overig vallen omdat hun eigenaar-rol twee domeinen heeft
     die verschillende kanten op wijzen. Die kiest de regel bewust niet voor je.

DE TOEWIJZINGEN HIERONDER zijn de uitkomst van dat tweede, met de hand beoordeeld op de INHOUD van
elke pagina. Alle drie bleken een bestaand governance-domein te hebben dat hun onderwerp dekt, dus
het zijn gewone domein-toewijzingen en geen kunstgreep: ze verschuiven vanzelf mee als zo'n domein
ooit anders geclassificeerd wordt.

Het commando is idempotent en dry-run by default, net als `wiki_zaad` en `wiki_broncheck`:

    python -m nooch_village.village wiki_domein            # rapport, schrijft niets
    python -m nooch_village.village wiki_domein --apply    # zet de toewijzingen
"""
from __future__ import annotations

import collections

from nooch_village import domeinen
from nooch_village.attachments import ARTEFACT_KINDS

#: artefact-id → (domein, waarom). Met de hand beoordeeld; elke regel draagt zijn reden, want
#: zonder reden is een handmatige indeling over een half jaar niet meer na te rekenen.
TOEWIJZINGEN: dict[str, tuple[str, str]] = {
    "NOTE-STRATE-001": ("Decision Making",
                        '"How we decide here" gaat over besluitvorming, niet over taalbeheer of '
                        "bio-materialen — de twee domeinen van de eigenaar-rol dekken het geen van "
                        "beide"),
    "TOOL-STRATE-001": ("Decision Making",
                        '"Decision coach" hoort bij dezelfde besluitvormingspraktijk'),
    "NOTE-BRANDV-001": ("Design system",
                        '"AI design instructions" beschrijft typografie, opmaak en kleurgebruik '
                        "van de pagina's: de componentlaag, niet merkpositionering"),
}


#: artefact-id → (bakje, waarom). HET NOODLUIK, en met opzet kort.
#:
#: Een gewone indeling loopt via een DOMEIN: het artefact draagt er een, of zijn rol doet dat.
#: Dat is de route die je wilt, want een domein is iets dat governance heeft toegewezen en dat
#: meebeweegt als de classificatie ooit verandert. Deze tabel slaat dat over en wijst rechtstreeks
#: een bakje aan.
#:
#: WANNEER DAT MAG: als er GEEN bestaand domein past. Niet als er geen domein past dat je mooi
#: vindt — dan hoort er een domein te komen. En omgekeerd, en dat is de eigenlijke regel:
#:
#:     EEN DOMEIN MAAK JE ALS DE PRAKTIJK EROM VRAAGT, NIET VOORAF OM EEN INDELING SLUITEND TE
#:     KRIJGEN.
#:
#: Dat is hetzelfde principe als waarom `domeinen.ROL_BAKJE` kort blijft: groeit zo'n tabel, dan
#: is dat een signaal dat er iets ontbreekt in governance — geen aanleiding om er hier een regel
#: bij te schrijven. Een domein verzinnen om één pagina op te bergen geeft een governance-record
#: waar niemand om vroeg, en dat is duurder dan deze ene regel.
OVERRIDES: dict[str, tuple[str, str]] = {
    "NOTE-STRATE-002": (
        "compliance-legal",
        '"Company information" draagt de registratiegegevens van de B.V. — KvK, btw, RSIN, IBAN, '
        "bestuurders en de douanecode. Geen van de achttien bestaande domeinen dekt dat, en de "
        "eigenaar-rol (strategic_lead_founder_steward) bezit alleen `bibliotheek` en "
        "`onderzoeksmethode`. Besluit Stefan, 24 september 2026: geen nieuw domein verzinnen voor "
        "één pagina; bewust via deze uitzonderingsroute."),
}


def _artefacten(att) -> list:
    uit = []
    for kind in ARTEFACT_KINDS:
        uit.extend(att.by_kind(kind, include_archived=True))
    return sorted(uit, key=lambda a: a.id)


def rapport(st) -> dict:
    """Waar landt alles, en wat vraagt nog een mens. Leest alleen."""
    recs = st.records.all()
    per_bak: dict[str, list] = collections.defaultdict(list)
    werklijst: list[tuple] = []
    for a in _artefacten(st.att):
        bak, waarom = domeinen.bakje_van(a, recs)
        per_bak[bak].append(a)
        if bak == domeinen.OVERIG:
            werklijst.append((a.id, a.title or a.id, waarom))
    return {"per_bak": dict(per_bak), "werklijst": werklijst, "totaal": len(_artefacten(st.att))}


def pas_toe(st, *, apply: bool = False) -> list[tuple]:
    """Zet de handmatige domeinen. Idempotent: wat al goed staat wordt overgeslagen.

    Geeft per regel terug wat er (zou) gebeuren, zodat de dry-run en de echte run dezelfde tekst
    opleveren en je ze naast elkaar kunt leggen."""
    uit = []
    for aid, (domein, reden) in TOEWIJZINGEN.items():
        a = st.att.get(aid)
        if a is None:
            uit.append((aid, "ontbreekt", "dit artefact bestaat hier niet", ""))
            continue
        if (a.domain or "").strip() == domein:
            uit.append((aid, "staat al goed", domein, a.title or ""))
            continue
        if domein not in domeinen.DOMEIN_BAKJE:
            # Fail-closed: een domein dat de tabel niet kent zou de pagina in Overig laten en
            # tegelijk de indruk wekken dat hij geplaatst is.
            uit.append((aid, "geweigerd", f"{domein!r} staat niet in de classificatietabel", ""))
            continue
        if apply:
            st.att.update(aid, domain=domein, change_note=f"domein gezet: {reden}")
        uit.append((aid, "gezet" if apply else "zou zetten", domein, a.title or ""))
    return uit


def pas_overrides_toe(st, *, apply: bool = False) -> list[tuple]:
    """Zet de bakje-overrides in `meta`. Idempotent, en hij VOEGT TOE aan de bestaande meta.

    Dat laatste is geen detail: de feiten van een pagina wonen in datzelfde `meta`, en
    `update(meta=…)` VERVANGT het woordenboek. Zou deze functie een vers `{"domein": …}`
    doorgeven, dan waren de feiten van die pagina weg — stil, en pas zichtbaar als iemand ze
    miste."""
    uit = []
    for aid, (bakje, reden) in OVERRIDES.items():
        a = st.att.get(aid)
        if a is None:
            uit.append((aid, "ontbreekt", "dit artefact bestaat hier niet", ""))
            continue
        if bakje not in dict(domeinen.BAKJES):
            uit.append((aid, "geweigerd", f"{bakje!r} is geen bestaand bakje", ""))
            continue
        huidig = dict(getattr(a, "meta", None) or {})
        if huidig.get("domein") == bakje:
            uit.append((aid, "staat al goed", bakje, a.title or ""))
            continue
        if apply:
            huidig["domein"] = bakje
            st.att.update(aid, meta=huidig, change_note=f"bakje-override: {reden}")
        uit.append((aid, "gezet" if apply else "zou zetten", bakje, a.title or ""))
    return uit


def rapport_tekst(rap: dict, acties: list[tuple], overrides: list[tuple] | None = None) -> str:
    overrides = overrides or []
    regels = [f"WIKI-INDELING — {rap['totaal']} artefacten", ""]
    for sleutel, label in domeinen.BAKJES:
        n = len(rap["per_bak"].get(sleutel, []))
        if n or sleutel == domeinen.OVERIG:
            regels.append(f"  {label:<36} {n:>4}")
    regels.append("")
    if rap["werklijst"]:
        regels.append("VRAAGT EEN MENS (valt in Overig):")
        for aid, titel, waarom in rap["werklijst"]:
            regels.append(f"  {aid:<18} {titel[:40]}")
            regels.append(f"      {waarom}")
    else:
        regels.append("Niets in Overig — elke pagina heeft een bakje.")
    regels.append("")
    regels.append("HANDMATIGE TOEWIJZINGEN:")
    for aid, wat, detail, titel in acties:
        regels.append(f"  {wat:<14} {aid:<18} {detail}")
    if overrides:
        regels.append("")
        regels.append("BAKJE-OVERRIDES (geen bestaand domein past):")
        for aid, wat, detail, titel in overrides:
            regels.append(f"  {wat:<14} {aid:<18} {detail}")
    return "\n".join(regels)
