# Drie open punten uit de brief, uitgezocht (20 september 2026)

Onderzoek, geen actie. Alle drie stonden al een tijd open onder "Wat hierna nog open staat".

Journal-bereik op de server: **vanaf 29 juni 2026**. Alles wat hieronder "nooit" heet, betekent
"niet in die periode, en niet in enig ander spoor dat ik kon vinden".

---

## 1. `orphan_report.py` — is hij ooit handmatig op de server gedraaid?

**JA.** Op **9 juli 2026 om 19:03:47 UTC**, als gebruiker `nooch`.

**Het bewijs, en waarom het houdt:**

| spoor | uitkomst |
|---|---|
| `__pycache__/orphan_report.cpython-314.pyc` | bestaat, mtime `2026-07-09 19:03:47`, eigenaar `nooch` |
| andere `.pyc`'s met diezelfde minuut | **nul** — hij staat er alleen |
| andere `.pyc`'s van die hele dag | **nul** (van de 361 op de machine) |
| laatste deploy die dag | 17:21 — ruim anderhalf uur eerder, dus geen deploy-bijvangst |
| bash-history root / nooch | leeg respectievelijk afwezig |
| cron, systemd-timer, journal | geen enkele verwijzing |

De sluitende schakel is een proef die ik heb gedaan in plaats van aangenomen: ik heb de lokale
`.pyc` weggegooid en `python -m nooch_village.orphan_report` gedraaid — **de `.pyc` verschijnt
opnieuw**. Een `-m`-run laat dus precies dit spoor achter.

**De enige mogelijke andere verklaring, eerlijk benoemd:** een kale `import
nooch_village.orphan_report` (bv. in een `python -c`) geeft hetzelfde spoor. Maar niets in de
codebase importeert deze module — alleen `tests/test_orphan_report.py`, en de suite draait niet op
prod — dus ook die variant is een mens die er bewust naar greep.

**Contrastgeval dat de redenering versterkt:** `link_suggest` en `projects_cli` hebben óók een
`.pyc`, maar met mtimes die **één seconde** uit elkaar liggen (`2026-07-05 06:09:12` en `:13`). Dat
is een bulk-compile, geen twee losse runs. Het orphan-spoor heeft die buur niet.

---

## 2. `village waarde_audit` en `village villageraad` — hoe vaak liepen ze, en ooit automatisch?

**Altijd handmatig. Nooit geautomatiseerd. En één van de twee bestaat niet meer.**

### waarde_audit
- **Eén run** in het hele journal: `Aug 26 20:31:28`, via `sudo -u nooch … village waarde_audit`.
- **Eén verslag** op prod: `data/output/waarde_audit_2026-08-26.md` (mtime `2026-08-28 07:57`; de
  mtime ligt ná de bestandsdatum, dus er is die ochtend nog iets mee gedaan — op dat moment werd
  hij ook gelezen, zie het journal).
- Geen cron, geen systemd-timer, geen aanroeper in de code.
- De `.pyc` is van 18 september, maar dat was een `python -c` die `wa.advies` importeerde om het
  gedrag te inspecteren — zichtbaar in het journal. Een inspectie, geen run.

### villageraad
- **Drie runs, alle drie op 26 augustus**: 10:21 (droog), 10:34 (droog), 10:49 (`--apply`).
- **Eén verslag**: `data/output/villageraad_2026-08-26.md`.
- **De module is op 20 september opgeheven** (`villageraad met pensioen; labels/rollen verhuisd
  naar org`). `village villageraad` bestaat dus niet meer als commando — de vraag "hoort iemand dit
  periodiek te draaien" is voor deze helft vervallen.
- Losse observatie: `data/villageraad.jsonl` staat er nog, **0 bytes**, mtime van vandaag 13:46 —
  een store die zichzelf aanmaakt maar nooit een regel heeft gekregen.

### De enige geautomatiseerde NoochVille-taak op de machine
`/etc/cron.d/nooch-verrijking`: `30 5 * * * nooch … village kb_verrijk_herkomst`. Verder draaien
alleen OS-timers (sysstat, logrotate, certbot). Dus: één cron, en die gaat niet over deze twee.

### Waarom dit ertoe doet
`afslanken` leest `data/output/waarde_audit_<datum>.md` als bron van waarheid. Dat bestand is er
één, van 26 augustus, uit één handmatige run. Elke afslank-beslissing die vandaag op die audit
leunt, leunt dus op een foto van 25 dagen oud, gemaakt vóór de hele opruiming van fase 1-12. Dat is
geen bug, maar het is wel de reden om hem opnieuw te draaien voordat `afslanken` weer iets doet.

---

## 3. `vastgelopen_route` / `naar_mens()` — is het dry-run-rapport per toewijzing herbeoordeelbaar?

**Nee. Per toewijzing is het een kale naam.** En de grond die er wél in staat, is sinds 20
september voor elk geval dezelfde zin.

**Wat het rapport per regel print** (`vastgelopen_route.rapport`):

```
    <rolnaam afzender>   <stap, 58 tekens>   → <ontvanger>
```

Geen grond, geen onderbouwing, geen alternatief. Daaronder staan twee tellingen: *waar landt het*
en *op welke grond*, allebei geaggregeerd.

**Twee dingen maken dat scherper dan "er ontbreekt wat uitleg":**

1. **De grond is een constante geworden.** `_mens_ontvanger` geeft sinds 20 september altijd de
   founder terug, met letterlijk `"alles wat vastloopt komt eerst bij jou"`. De tabel "op welke
   grond" heeft dus per definitie één regel met N erachter. Hij is niet verkeerd, hij is leeg —
   informatie die voor elk geval hetzelfde is, onderscheidt niets.
2. **Het enige per-geval-oordeel wordt wél verzameld en NIET getoond.** `suggestie` (`"voorstel:
   dit lijkt van <rol> — <waarom>"`) zit in elk item van het verslag en wordt nergens geprint: niet
   per regel, niet in een telling. Dat is precies het veld waarmee je een toewijzing zou kunnen
   herbeoordelen.

**Wat het zou kosten om het wél herbeoordeelbaar te maken:** één printregel. De data zit al in
`verslag["geland"]` (`grond` én `suggestie` per item). Niet gebouwd — dit was een onderzoeksvraag.

**Hoe vaak is hij gedraaid:** één keer op prod, `Aug 29 11:56`, droog (geen `--apply` in de
commandoregel). De `--apply`-tak heeft dus nog nooit op productie gelopen.
