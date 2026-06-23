# Inbox-analyse — wat het dorp heeft gevoeld

Doel: per pending human-inbox-item begrijpen **wat de spanning is, wie het sensde, en
hoe het gesensed werd**. Dit is de voorbereiding op het inbox-herontwerp. Het bijzondere:
dit zijn geen door mensen ingevoerde taken, maar spanningen die het dorp zelf heeft gevoeld
en bewust níét zelf heeft opgelost (mens-gated).

## De gedeelde sensing-pijplijn

De meeste items ontstaan via dezelfde trechter:

1. Een rol voelt iets via `sense_tension(...)` (operationeel of governance).
2. `gap_classifier.classify_gap` bepaalt de **mandaat-overlap** met bestaande rollen en
   classificeert in:
   - **A** = een rol dekt het operationeel (overlap hoog) → de rol handelt zelf, geen inbox.
   - **B** = een rol is de dichtstbijzijnde eigenaar (overlap ≥ 0.10) → `means_gap` in de inbox,
     met die rol als kandidaat-eigenaar.
   - **C** = géén rol haalt de drempel (overlap < 0.10) → `suggestion` in de inbox: kandidaat
     voor een nieuw voorstel, puur ter inspectie, geen automatische geboorte.
3. Een LLM-**B-observer** (`coherence_observer`) toetst of de spanning coherent geformuleerd is.
4. Het item landt in `data/human_inbox.json` en wacht op een menselijk besluit.

Kernprincipe: een rol mag een gat **signaleren en een voorstel schrijven**, maar nooit zelf
code uitvoeren, een API aanroepen of een rol geboren laten worden. Dat is de geboren-versus-
bemenst-grens.

Item-typen die we tegenkomen: `suggestion` (gap C), `means_gap` (gap B), `escalation`
(governance-voorstel dat G1-G4 niet haalde), `activation` (onbemande rol wacht op implementatie),
`keyword` (kandidaat-woord dat de Librarian escaleerde), `keyword_batch` (meet-batch wacht op
credit-akkoord).

---

## Item 1 — `ngram_2019_cutoff` (suggestion) · 20 juni 16:18 · `2d8333a29ac0`

**Aard van het gat:** HARDGECODEERD (mens-geschreven bekende limiet), niet dynamisch ontdekt.

**De spanning.** De ngram-databron (Google Books Ngram) stopt in 2019. Het dorp mist daarmee
7 jaar culturele taalverschuiving (2019-2026); geen enkele puls kan recente verschuivingen in
missie-termen signaleren.

**Wie senste het.** `harry_hemp` — de rol die de lange culturele taalverschuiving observeert
via ngram.

**Hoe gesensed (eerlijk).** Harry *ontdekt* dit niet. In `HarryHemp._reflect()` staan twee
`_report_means_gap(...)`-regels met letterlijk vooraf geschreven tekst; een ontwikkelaar wist
dat ngram in 2019 stopt en heeft die observatie ingebouwd. Elke reflectie-cyclus roept Harry die
zin opnieuw af. Dit is de `force=True`-variant: een structureel bekende limiet, geen analyse van
de eigen data. Wat wél autonoom is, zit stroomafwaarts: de `gap_classifier` rekent live de
mandaat-overlap uit (hoogste 0.083 < drempel 0.10) → uitkomst **C** → `add_suggestion`; en de
B-observer (Gemini) toetst zelf de coherentie. Dus: inhoud = mensenwerk, afhandeling = autonoom.

**Serieuze beoordeling van de spanning.** Bij serieus kijken klopt "serpapi dekt het al" niet
zomaar: ngram is een *boek-/cultuurtaal*-signaal over decennia, serpapi_trends is een *zoek*-signaal
over maanden. Andere bron, ander doel. Maar: voor een instrument dat de lange boog meet (1950-2019)
is een cutoff op 2019 een kleine degradatie, geen kritieke blinde vlek. En de behoefte aan een
*recent* signaal is bij ontwerp al belegd bij andere rollen (website_watcher via serpapi_trends,
trends via GSC). De classifier zag dit niet, want die toetst alleen *accountability-tekst-overlap*,
niet *skill-niveau-dekking*. Dat is zelf een inzicht voor het herontwerp.

**Besluit voor de mens (open).** Drie serieuze opties:
- (a) een echte recente cultuurtaal-bron bouwen voor Harry — maar er is geen makkelijke gratis
  post-2019 ngram-equivalent; veel werk, twijfelachtige opbrengst;
- (b) het gat expliciet ACCEPTEREN: ngram blijft het lange-boog-instrument, recent signaal komt
  van website_watcher/trends; documenteer die taakverdeling en stop het terugkerende zelf-signaal;
- (c) uitstellen.
Aanbeveling: (b). Reversibel.

**Gekozen resolutie (samen ontworpen).** Optie (a), maar slim: Harry niet vervangen maar
verdiepen met wat hij al heeft. Drie-traps methode:
1. **Lange-boog-correlaties** in ngram: co-beweging (samen op) en substitutie (de een verdringt
   de ander, negatieve correlatie) tussen missietermen. Relatieve frequenties, dus vergelijkbaar.
2. **OpenAlex relatieve-aandacht** per term per jaar (aandeel van alle werken dat jaar, NIET ruwe
   aantallen — anders schijn-stijging door groeiend publicatievolume/indexering).
3. **Overlap-kalibratie:** correleer ngram vs OpenAlex over de gedeelde jaren (~2000-2019). Sterke
   correlatie → OpenAlex is een verdedigbare voortzetting voorbij 2019, mét gemeten betrouwbaarheid;
   zwakke correlatie → de brug is wankel, zwaar labelen of laten. Kalibratie i.p.v. blind plakken.

**Voortgang.**
- ✅ Stuk 1 gebouwd: `ngram_correlate.py` (pearson + `correlate_terms` → co-beweging/substitutie),
  en de ngram-skill levert nu de volledige `timeseries` per term mee. 9 tests + mutatie-check.
- ⏳ Stuk 1b: Harry de engine laten draaien op de missietermen en de sterkste co-beweging +
  substitutie rapporteren (tijdgeest-observatie).
- ✅ Stuk 2a: OpenAlex `mode='yearly'` → relatieve academische aandacht per jaar (aandeel, niet
  ruw). 7 tests.
- ✅ Stuk 2b: `years_dict` + `calibrate` (pearson over gedeelde jaren) + `continue_arc` (anker=100,
  ngram t/m anker + OpenAlex daarna). 7 tests.
- ✅ Stuk 2c: `assess_continuation` (alleen voortzetten bij r >= 0.5) + `HarryHemp._extend_arcs`
  (per term OpenAlex-jaarreeks, ankert op corpus-eindjaar, rapporteert vertrouwde voortzetting
  met gemeten r). 3 tests.
- ✅ Reflectie opgeruimd: `ngram_2019_cutoff` niet meer gesenst (gat is gedekt); `nl_corpus_coverage`
  blijft (= item 2, los verhaal).
- ✅ Inbox-item `2d8333a29ac0` gesloten (approved) met de gemeten uitkomst als reden.
- ⏳ Roldefinitie via governance: `python -m nooch_village.village upgrade_harry_role` (amend_role,
  draait op de Mac).

**STATUS ITEM 1: OPGELOST.** Van "ik mis 7 jaar" naar een rijkere rol: structurele co-beweging/
substitutie over de lange boog + een gekalibreerde, transparant gelabelde voortzetting voorbij 2019.
