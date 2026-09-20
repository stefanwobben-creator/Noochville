"""De inbox wordt DM — stap A van twee: SCHRIJVEN, niets verwijderen.

Besluit Stefan, 20 september 2026: *"alles wat tot dusver in de inbox is gekomen kon ik niet echt
veel mee, dus dat werkte sowieso niet, dus ook niet om te houden — als er iets gesignaleerd is kan
het gewoon naar een DM en dan is de mens verantwoordelijk."*

Daarmee vervalt het eerdere ontwerp (een vijfde kanaalsoort `role:<id>` met de verwerkingsstate
erin). Er gaat **geen** state mee: geen read/processed/archived, geen outcome, geen poort-oordeel.
Het wordt een gewoon bericht. De ontvanger is verantwoordelijk, zoals bij elk ander bericht.

TWEE STAPPEN:
  A. migreren (deze module) — `NotifStore` en `/inbox` blijven staan, uitkomst te bekijken
  B. opruimen — `NotifStore`, `/inbox`, `/inbox/verwerk` en de lade eruit

DE ROUTERING, in deze volgorde. `target_type` beslist, niet `entry_id` — die twee verzamelingen
raken elkaar nauwelijks (33 persoon-gerichte rijen waarvan 3 een `entry_id` dragen; 24 rijen met
`entry_id` waarvan er 21 rol-gericht zijn).

  1. doel is een PERSOON        → DM naar die persoon
  2. doel is een ROL met precies één mens-vervuller → DM naar die mens.
     Dit geldt óók als de rol gearchiveerd is: `noochville__circle_lead` (49 rijen) en
     `the_source` (36) zijn opgeheven maar nog aan een mens toegewezen, en 85 berichten mogen niet
     van de volgorde van twee checks afhangen.
  3. doel is een ROL zonder mens-vervuller → DM naar de terugval (de founder).
  4. doel is een ROL met MEER DAN ÉÉN mens-vervuller → **niet migreren**, rapporteren.
     Elf rijen op drie rollen (`mother_earth__nooch`, en twee circle_leads) hebben Lotte én Stefan.
     Naar beiden is het bericht dubbel, naar de eerste is willekeur, naar de founder is een aanname.
     Dat is een keuze van een mens; de migratie parkeert ze en zegt het.

DE TEGENPARTIJ IS MEESTAL GEEN PERSOON. Bij 333 van de 338 rol-rijen is `by` een rol- of
systeemnaam (`compliance` 69, `claims-checker` 46, `harry_hemp` 45, …). Het DM-id draagt die naam
dan als tegenpartij. Dat is bewust: de bron blijft zichtbaar en de signalen blijven per bron
gegroepeerd. `views/messages` haalt het antwoordveld weg zodra de tegenpartij geen persoon is —
antwoorden aan iets dat niet leest is het dead-letter-patroon, en een antwoordveld dat niets
bereikt is erger dan geen antwoordveld.
"""
from __future__ import annotations

from nooch_village import channels, signaal

# De routering woont in `signaal.py`, want `cockpit2` gebruikt hem ook voor alles wat vanaf nu
# ontstaat. Twee kopieën zouden betekenen dat dezelfde rol-id vandaag bij de een landt en morgen
# bij de ander, zonder dat iets zich meldt.
TERUGVAL_ROL = signaal.TERUGVAL_ROL
NAAR_PERSOON, NAAR_VERVULLER = signaal.NAAR_PERSOON, signaal.NAAR_VERVULLER
NAAR_TERUGVAL, MEERDERE, ONBEKEND = signaal.NAAR_TERUGVAL, signaal.MEERDERE, signaal.ONBEKEND


def ontvanger_van(st, n: dict) -> tuple[str, str]:
    """(persoon_id, reden). Lege persoon_id = niet te routeren; de reden zegt waarom.

    DE MIGRATIE PARKEERT bij meerdere vervullers, terwijl een NIEUWE melding naar allemaal gaat
    (`signaal.stuur`). Dat verschil is bewust: historie hoort precies één plek te hebben, en een
    mens beslist welke; nieuw werk mag liever dubbel aankomen dan nergens."""
    wie, reden = signaal.ontvangers(st, n.get("target_type"), n.get("target_id"))
    if reden == signaal.MEERDERE or len(wie) != 1:
        return "", reden
    return wie[0], reden


def migreer(notif, st, *, apply: bool = False) -> dict:
    """Elke notificatie als DM-bericht. `apply=False` schrijft niets.

    Idempotent: een rij die al in het kanaal staat wordt overgeslagen. Het rapport draagt zijn
    eigen bewijs — een migratie die dat niet doet, is een bewering."""
    rijen = notif.all()
    r = {"rijen": len(rijen), "geschreven": 0, "bestond_al": 0, "geparkeerd": 0,
         "per_reden": {}, "kanalen": {}, "geparkeerde_rollen": {}, "apply": apply}
    for n in rijen:
        ontvanger, reden = ontvanger_van(st, n)
        r["per_reden"][reden] = r["per_reden"].get(reden, 0) + 1
        if not ontvanger:
            r["geparkeerd"] += 1
            sleutel = f"{n.get('target_type')}:{n.get('target_id')}"
            r["geparkeerde_rollen"][sleutel] = r["geparkeerde_rollen"].get(sleutel, 0) + 1
            continue
        kanaal = channels.dm_kanaal(str(n.get("by") or "village"), ontvanger)
        r["kanalen"][kanaal] = r["kanalen"].get(kanaal, 0) + 1
        if not apply:
            bestaat = any(e.get("id") == n.get("id")
                          for e in st.channels.trail(kanaal, limit=10_000))
            r["bestond_al" if bestaat else "geschreven"] += 1
            continue
        if st.channels.plaats_notificatie(kanaal, n) is None:
            r["bestond_al"] += 1
        else:
            r["geschreven"] += 1

    if apply:
        geplaatst = sum(1 for k in r["kanalen"]
                        for e in st.channels.trail(k, limit=10_000)
                        if e.get("kind") == channels.NOTIFICATIE)
        r["berichten"] = geplaatst
        r["klopt"] = geplaatst + r["geparkeerd"] == r["rijen"]
    return r


def rapport_tekst(r: dict) -> str:
    regels = [f"notificaties       : {r['rijen']}",
              f"geschreven         : {r['geschreven']}",
              f"bestond al         : {r['bestond_al']}",
              f"geparkeerd         : {r['geparkeerd']}",
              f"DM-kanalen         : {len(r['kanalen'])}", "", "routering:"]
    for reden, n in sorted(r["per_reden"].items(), key=lambda x: -x[1]):
        regels.append(f"   {reden:<22}{n:>5}")
    if r["geparkeerde_rollen"]:
        regels += ["", "geparkeerd (een mens moet kiezen):"]
        for doel, n in sorted(r["geparkeerde_rollen"].items(), key=lambda x: -x[1]):
            regels.append(f"   {doel:<52}{n:>4}")
    regels.append("")
    if not r.get("apply"):
        regels.append("◌ droogloop — er is niets geschreven. Draai opnieuw met --apply.")
        return "\n".join(regels)
    regels.append(f"berichten in de kanalen: {r['berichten']}  "
                  f"(+ {r['geparkeerd']} geparkeerd = {r['rijen']})")
    regels.append("✓ alles verantwoord" if r["klopt"] else "✗ ER IS IETS KWIJT — niet doorgaan")
    return "\n".join(regels)
