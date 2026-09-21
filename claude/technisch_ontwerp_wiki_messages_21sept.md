# Technisch ontwerp — Wiki inline-editen + Messages-kanaalmodel

Antwoord op `claude/ontwerp_notion_stijl_wiki_en_messages_21sept.md`. **Nog niets gebouwd.**
Alle getallen hieronder zijn op productie gemeten op 21 september 2026.

---

## Deel 1 — Wiki: inline editen

### Wat er nu staat (gelezen in de code, niet gegokt)

`views/wiki.py::render_pagina` rendert de body twee keer zodra je bewerkt:

1. `<div class='att-body'>` met `_body_html(a.body)` — de opgemaakte tekst;
2. `_artefact_edit_form(a, …)` uit `views/overview.py` — een `<details>` met een TITLE-input en
   `md_editor('body', a.body)`: een `<textarea>` met de ruwe markdown plus een mini-toolbar.

Dat is precies de tweede kopie die eruit moet. De opslag-kant is klein en gezond en blijft:
één `artefact_edit`-actie → `st.att.update(...)` → één versie-entry `"bewerkt"`.

### De opmaaktaal is klein genoeg om dit zonder library te doen

`_md` (cockpit2_util.py) kent exact zes dingen:

| markdown | html |
|---|---|
| `**vet**` | `<strong>` |
| `*cursief*` | `<em>` |
| `~~door~~` | `<del>` |
| `## kop` | `<h4>` |
| `- item` | `<ul class='fbul'><li>` |
| `[tekst](url)` (alleen http/https) | `<a>` |

Plus de wiki-laag: `[[verwijzing]]` → pill/chip (dat gebeurt ná `_md`, in `_body_html`).
Zes constructies is klein genoeg voor een eigen serializer en te klein om ProseMirror/TipTap/
Quill binnen te halen.

### De keuze: de serializer draait op de SERVER, niet in de browser

**Aanpak:** de body wordt één `contenteditable`-gebied op de plek waar hij al staat. Bij opslaan
post de pagina de `innerHTML` van dat gebied; de **server** zet dat om naar markdown en slaat
markdown op. Opslag blijft dus ongewijzigd markdown; HTML wordt nooit opgeslagen.

**Waarom niet in JS:** er zou dan een tweede opmaak-kenner bestaan naast `_md`, en die twee lopen
uiteen zodra er één regel bijkomt. Dat is precies de afweging die al één keer in dit scherm is
gemaakt: de voorbeeldknop haalt zijn weergave op bij `/md-preview` (dus bij `_md` zelf) "niet bij
een tweede parser in JS, want die twee lopen uiteen zodra er één opmaakregel bij komt"
(`nooch.js`). Hetzelfde argument, dezelfde kant op.

**Bijvangst:** een Python-serializer is met pytest te testen, een JS-serializer niet — er is in
deze stack geen JS-testrunner. Ik wil de heen-en-weer-eigenschap kunnen bewijzen op de echte
pagina's, niet alleen met de hand kunnen naklikken.

**Nieuw:** `_md_naar_bron(html) -> str` naast `_md` in `cockpit2_util.py`, met een **gesloten
whitelist** (`STRONG/B`, `EM/I`, `DEL/S`, `A`, `H4`, `UL/LI`, `BR`, `DIV`, `P`, tekst, plus de
`[[link]]`-pill). Fail-closed: een tag die er niet in staat wordt zijn eigen tekst, nooit ruwe
HTML. Geparsed met `html.parser` uit de standaardbibliotheek, geen dependency.

**De poort die het eerlijk houdt:** een test die voor elke echte pagina op prod bewijst dat
`_md_naar_bron(_md(body)) == body` (op witruimte genormaliseerd). Loopt dat ergens stuk, dan
komt die pagina in de test te staan als bekend geval — niet stilletjes als dataverlies bij de
eerste bewerking.

### Wat je op het scherm ziet

- De `.att-body` wordt bij bewerken zelf `contenteditable`, op zijn plek, met de opmaak zichtbaar.
- Geen tweede kopie, geen scroll naar een ander blok: de opslaan-balk verschijnt in beeld bij de
  tekst (zelfde `data-qadd-dirty`-mechaniek: pas zichtbaar als er echt iets veranderd is).
- De titel wordt op dezelfde manier inline bewerkbaar (`<h1>` → contenteditable), niet als
  los TITLE-veld.
- De toolbar (B/I/S/•/H) blijft, maar zweeft boven de tekst i.p.v. boven een textarea, en werkt
  via `document.execCommand('bold'|'italic'|'strikeThrough')` — dat produceert exact de tags die
  in de whitelist staan.
- Eén submit, één `artefact_edit`, één versie-entry. Ongewijzigd.

### Wat NIET verandert

Geschiedenis (`_artefact_versions_html`), Facts, Links/backlinks, de voorstel-route voor wie
geen eigenaar is (`pagina_voorstel`), de authz-poort (`_artefact_gate`), en `_md` zelf.

### Risico's die ik nu al zie

1. **Browsers maken eigen HTML bij Enter en bij plakken** (`<div>`, `<p>`, soms `<span style>`).
   Ondervangen door de whitelist (alles onbekends → tekst) plus `paste`-afvanging die als platte
   tekst invoegt. Dat laatste is één regel JS en voorkomt dat er Word-opmaak binnenkomt.
2. **Verlies bij een pagina die markdown bevat die `_md` niet kent** (bijv. `# ` met één hekje,
   tabellen). `_md` rendert die vandaag al als platte tekst, dus er gaat niets verloren dat nu
   wél werkt — maar de round-trip-test moet dit aantonen, niet mijn redenering.
3. **Geen JS = geen bewerken.** Nu is er een `<details>` die ook zonder JS werkt. Ik houd daarom
   de bestaande textarea-vorm als `<noscript>`-val achter de hand; anders is dit een functieverlies
   dat niemand opmerkt tot het moment dat het telt.

---

## Deel 2 — Messages: kanalen zijn bewust

### Gemeten op prod (21 september 2026)

| wat | nu |
|---|---|
| projectkanalen met gesprek (vullen de lijst) | **123** |
| doelen (open) | **5** — Website, STCB, MITH, Batch 4, Supply chain |
| cirkelkanalen (levend) | **2** — Mother Earth (wortel) en Nooch; beide nog zonder enig bericht |
| losse kanalen ("+ new channel") | **0** — nooit gebruikt |
| mensen | 5 |
| DM-kanalen | 42 (zie de inventarisatie) |

### De databron voor "in mijn lijst": een eigenschap van de MENS

**Keuze:** `people.json`, naast de bestaande `gezien`-sleutel. Nieuw: `PeopleStore.volg(pid,
kanaal)`, `ontvolg(pid, kanaal)`, `gevolgd(pid) -> dict`.

Waarom daar, en niet als nieuwe store of als vlag op het kanaal:

- Het is letterlijk dezelfde soort feit als `gezien`: *"wanneer heb ík dit gelezen"* naast
  *"wil ík dit in mijn lijst"*. De motivering staat al uitgeschreven in `people.py` en geldt
  woord voor woord ook hier.
- Een vlag op het KANAAL zou fout zijn: dan volgt iedereen hetzelfde, en bij een tweede mens
  drijft het uiteen. (`reference, don't copy`.)
- Een nieuwe store is een besluit dat `tests/test_conventies_ratchet.STORES` bewust bevriest.
  Dit ontwerp voegt **geen store toe** en **migreert geen berichten**.

`project["log"]` blijft waar het is. Een projectkanaal houdt op te bestaan in de LIJST, niet in
de data — precies de "ongefilterd uit het zicht"-variant uit je vraag. Geen migratie, dus ook
geen kans op verlies.

### De structuur van de lijst

```
General            → het kanaal van de wortelcirkel (bestaat al: circle:<root>), altijd zichtbaar
Goals              → één kanaal per open doel: goal:<doel_id>  (5 stuks, automatisch aanwezig)
Channels           → losse kanalen, bewust aangemaakt (topic:<id>, bestaat al)
Projects           → ALLEEN wat jij volgt (nu: leeg tot je iets toevoegt)
Direct             → ongewijzigd
```

**Goal-kanalen als nieuw soort `goal:<doel_id>`**, niet als vooraf aangemaakte losse kanalen met
de doelnaam erin. Reden: het id verwijst dan naar het doel, en hernoemt een mens het doel, dan
volgt het kanaal vanzelf. Een topic met de naam "MITH" is een kopie van de taxonomie die gaat
afwijken. Opslag: `channels.json`, dezelfde `post`/`trail` als een topic — er komt geen tweede
opslagmechanisme bij.

**Cirkels:** er zijn er twee en ze zijn allebei nog leeg. De wortelcirkel (Mother Earth) wordt
"General"; dan blijft er één over, Nooch. *(Dit is het enige punt waar ik jouw model moet invullen:
het ontwerpdocument noemt cirkels niet. Blijft Nooch als eigen kanaal staan, of valt hij samen met
General? Ik raak in beide gevallen geen data aan — er staat niets in.)*

### Zoeken en toevoegen

- Het bestaande `FIND A CHANNEL`-veld zoekt over **alles**, inclusief projectkanalen die je niet
  volgt. Een treffer die je niet volgt krijgt een `+ add`-knop naast de naam.
- **Openen = toevoegen**, precies zoals in je opdracht ("pas als je 'm opent/toevoegt"). Op het
  kanaal zelf staat een `remove from list`-knop, zodat het omkeerbaar is.
- Op de projectkaart komt een link naar zijn gespreksdraad; die volgt hetzelfde pad.

### Eenmalige seed, zodat de eerste login geen dataverlies lijkt

Zonder seed ziet iedereen bij de eerste keer een lege Projects-groep terwijl er 123 gesprekken
bestaan. Voorstel: volg bij de omschakeling per mens de projectkanalen **waarin die mens zelf
heeft geschreven**. Gemeten: **Stefan 19, Lotte 2, de overige drie 0.** Van 123 naar 19 is het
punt van deze opdracht; van 123 naar 0 is iets anders.

Zelfde discipline als stap 6 en de voorstellen-opruiming: vingerafdruk vooraf, droge run
standaard, veldvergelijking achteraf. Alleen `people.json` wordt aangeraakt.

### Inbox: wat er werkelijk staat (afwijking van de opdracht, bewust gemeld)

De opdracht zegt "Inbox-navigatie-item én -route eruit". **De route bestaat niet.** `/inbox` staat
niet in `do_GET` (en dus niet in de route-tabel van `docs/ARCHITECTUUR.md`); er is geen
`views/inbox.py`.

Sterker: **de knop is al dood.** `_nav()` rendert `onclick='ibxToggle()'`, en `ibxToggle` is
nergens gedefinieerd — niet in `nooch.js`, niet in `_NAV_JS`, nergens in de repo. De docstring
ernaast verwijst naar `render_inbox_chrome`, een functie die niet bestaat. Klikken op Inbox doet
vandaag dus niets, op een JS-fout in de console na.

Wat ik weghaal: de knop uit `_nav()`, de bijbehorende dode `ibx-*`-CSS, de `/inbox`-link onderaan
`views/messages.py`, en de test `test_de_inbox_is_een_lade_geen_pagina` (die bewaakt nu het
bestaan van een dode knop). Een route verwijderen kan ik niet — er is er geen.

---

## Volgorde, omvang en poorten

| # | stuk | raakt | eigen PR |
|---|---|---|---|
| 1 | Inbox-knop + dode `ibx`-CSS eruit | `cockpit2_util.py`, `nooch.css`, `messages.py`, 1 test | ja (klein, los te mergen) |
| 2 | `_md_naar_bron` + round-trip-test op de echte paginas | `cockpit2_util.py`, tests | ja (geen UI-wijziging) |
| 3 | Wiki inline-editor op die serializer | `views/wiki.py`, `nooch.js`, `nooch.css` | ja |
| 4 | `PeopleStore.volg/ontvolg` + `goal:`-kanaalsoort | `people.py`, `channels.py` | ja (geen UI-wijziging) |
| 5 | Messages-lijst op het nieuwe model + zoeken/toevoegen | `views/messages.py`, `cockpit2.py` | ja |
| 6 | Seed van de gevolgde projectkanalen (droge run eerst) | `people.json` op prod | data, geen PR |

2 en 4 leveren eerst de laag zonder zichtbare verandering; 3 en 5 zetten het scherm erop. Zo is
elke stap los terug te draaien en staat er nooit half werk live.

**Per scherm 3-5 tests, volle suite voor en na, UI volgens atoms → molecules → patterns,
`arch_map` bijwerken bij de nieuwe dispatch-acties** (`kanaal_volg`, `kanaal_ontvolg`).

---

## Waar ik jouw antwoord op nodig heb

1. **Het Nooch-cirkelkanaal** (het enige dat naast General overblijft, en leeg): eigen regel in
   de lijst, of samen met General?
2. **De seed** (Stefan 19, Lotte 2): doen, of begin je liever met een lege lijst?
3. **`<noscript>`-val bij de wiki-editor**: houd ik de oude textarea-vorm achter de hand voor
   het geval JS niet draait, of mag bewerken JS vereisen?
