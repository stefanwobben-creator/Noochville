# Technisch ontwerp — een bestand in een chatbericht

**Nog niets gebouwd.** Alle getallen zijn op 22 september 2026 op productie gemeten.

---

## Eerst een correctie op de aanname

De opdracht zegt dat het enige upload-pad de PDF-naar-kennisbank is, en dat dat geen bruikbaar
patroon is. Het eerste klopt niet: er zijn er **twee**, en de andere is gezond en draait.

| pad | staat | omvang op prod |
|---|---|---|
| `kb_intake_pdf` / `kb_atoom_ref_pdf` (kennisbank) | **stuk** | 5 bestanden |
| `attach_file` (projectbijlagen) | **werkt** | **48 bestanden, 83 MB** |

De kennisbank-bugs zijn bevestigd: `kb_intake` en `atomiseer` worden aangeroepen maar nergens
geïmporteerd — `NameError` zodra je de knop indrukt. Terecht geen patroon.

Maar `attach_file` heeft precies wat hier nodig is en is in productie beproefd: multipart-parser,
groottegrens vóór het wegschrijven, pad-ontsmetting, een serveer-route, en een wezen-rapport
(`orphan_report.py`) dat bestanden vindt die nergens meer aan hangen. **Dat is het patroon dat ik
hergebruik**, niet een derde upload-weg.

---

## 1 · Waar landen bestanden, en hoe lang

**Waar:** `data/kanaalbijlagen/<kanaal>/<uuid8>_<schone-naam>`, parallel aan het bestaande
`data/attachments/<pid>/…`. Zelfde schijf, dus automatisch mee in de pre-deploy-backup
(`tar czf backups/… data/`) en in de eigendom-sweep.

**Wat er in de DATA komt:** een `bijlagen`-lijst op het BERICHT, niet op het kanaal:

```python
e["bijlagen"] = [{"id", "name", "stored", "size", "mime", "at"}]
```

Dat is dezelfde vorm als `reactions`, en om dezelfde reden: een kanaalbericht heeft twee
achterkanten (een projectkanaal is `project["log"]` via de ledger, de rest staat in
`channels.json`). Door het aan het BERICHT te hangen werkt één mechanisme op allebei — precies wat
`ChannelStore.add_reaction` vorige week al bewees.

**Hoe lang: zolang het bericht bestaat, en dat is voorlopig altijd.** Een kanaalbericht kan vandaag
niet verwijderd worden, dus een bijlage verdwijnt niet vanzelf. Dat is een KEUZE en geen omissie —
een gesprek waarin het bestand waar het over ging is opgeruimd, leest als een gat — maar het
betekent dat de schijf groeit. Wat erbij hoort:

- `village bijlage_wezen` in de stijl van `orphan_report.py`: bestanden op schijf die aan geen enkel
  bericht meer hangen. Rapporteren, niet automatisch wissen.
- Geen retentietermijn en geen automatische opruiming. Komt die er ooit, dan als een mens-besluit
  per bestand, niet als een cron die stil dingen weggooit.

---

## 2 · Types en grootte

**Grootte: de bestaande grens, geen tweede.** `_upload_max_bytes()` → 20 MB, instelbaar via
`upload_max_bytes`, bewust onder de nginx-cap van 25 MB zodat de app zelf de nette fout geeft.
`_upload_error()` geeft al "Bestand te groot (max 20 MB)" met een 413. Beide ongewijzigd
hergebruiken.

**Types: een allowlist, en dat is nieuw.** Het projectpad accepteert álles en raadt bij het serveren
het mimetype. Voor bijlagen in een gesprek doe ik dat niet:

| categorie | extensies | hoe geserveerd |
|---|---|---|
| afbeelding | png, jpg, jpeg, webp, gif | inline (voorbeeld in de draad) |
| document | pdf | inline |
| tekst/data | txt, md, csv | download |
| office | docx, xlsx, pptx | download |
| **al het andere** | — | **geweigerd bij het uploaden** |

Fail-closed op de EXTENSIE én op wat de browser als type meestuurt; komen die niet overeen, dan
weigeren. Geen inhoudsdetectie — dat suggereert een zekerheid die een extensiecontrole niet geeft.

---

## 3 · Wie mag een bijlage zien

**Exact wie het kanaal mag lezen. Eén regel, geen tweede.**

De serveer-route wordt `GET /bijlage?kanaal=<id>&id=<bijlage-id>` en die controleert het
LEESRECHT OP HET KANAAL, server-side, bij elk verzoek:

- `dm:` → je moet deelnemer zijn (`dm_leden`), zoals `kanalen_van` al bepaalt;
- `circle:` · `goal:` · `topic:` → iedereen die is ingelogd (zo staat de lijst nu);
- `project:` → het leesrecht van dat project (zie het gat hieronder).

**De URL is géén sleutel.** Wie de link doorstuurt geeft geen toegang weg: de ontvanger moet zelf
door dezelfde poort. Daarom ook geen pad-gebaseerde URL (`/kanaalbijlagen/…`) maar een route die
eerst vraagt en dan pas leest.

**Twee harde regels bij het serveren**, omdat ons eigen domein de sessie draagt:

- `X-Content-Type-Options: nosniff` op alles;
- inline alleen voor de afbeeldingen en PDF hierboven; al het andere met
  `Content-Disposition: attachment`. Nooit `text/html` of `image/svg+xml` inline — een geüploade
  SVG die als afbeelding wordt geserveerd voert script uit op onze eigen origin.

### Gat dat ik hierbij vond, in het BESTAANDE pad

`GET /file?pid=&aid=` doet **geen enkele leescheck**: hij zoekt het project op, pakt de bijlage en
stuurt de bytes. Elke ingelogde gebruiker kan zo elk projectbestand ophalen, ook van een project met
`private: True`. Op prod staan er 48 bestanden achter die route. Dat is niet mijn scope en ik heb
het niet aangeraakt — maar dezelfde poort die ik voor kanaalbijlagen bouw, past er één-op-één op.
**Zeg het als je dat in dezelfde beurt dicht wilt.**

---

## 4 · En een rol-kanaal dan

Een rol-kanaal (de groep "Roles & system" uit gisteren) heeft geen mens aan de andere kant.
`kan_antwoorden()` geeft daar al `False` en het scherm toont geen antwoordveld, met de reden
erbij: *"een antwoordveld dat niets bereikt is erger dan geen antwoordveld — dat is het
dead-letter-patroon"*.

**De upload-knop volgt exact die voorwaarde.** Geen tweede regel, geen eigen uitzonderingslijst:
staat er een antwoordveld, dan staat er een paperclip; staat het er niet, dan ook geen paperclip.
Een bestand uploaden naar een kanaal dat niemand leest is hetzelfde dead letter, maar dan eentje
die 20 MB schijf kost.

**Andersom kan wél, en dat is geen tegenstrijdigheid.** Een rol of het systeem zou ooit een bericht
mét bijlage kunnen PLAATSEN (een gegenereerd rapport, een export). Dat werkt zonder wijziging,
want de bijlage hangt aan het BERICHT en niet aan de afzender. Richting uit is dus open, richting
in dicht — precies zoals het nu voor tekst al is.

---

## Wat ik NIET doe

- **Geen nieuwe store.** De bijlage is een veld op een bestaand bericht; `test_conventies_ratchet`
  bevriest de store-lijst bewust.
- **Geen tweede groottegrens** en geen eigen upload-route: de bestaande multipart-tak in `do_POST`
  krijgt er één actie bij.
- **De kennisbank-bugs niet meenemen.** Die zijn echt, maar het is een ander scherm en een andere
  keten; ze hier meenemen maakt deze scope onbeoordeelbaar. Aparte melding waard.

---

## Samengevat

| vraag | antwoord |
|---|---|
| waar | `data/kanaalbijlagen/<kanaal>/…`, veld op het bericht |
| hoe lang | zolang het bericht leeft; geen auto-opruiming, wel een wezen-rapport |
| grootte | 20 MB — de bestaande `_upload_max_bytes`, ongewijzigd |
| types | allowlist: afbeelding + pdf inline, tekst/office als download, rest geweigerd |
| wie ziet het | wie het kanaal mag lezen, server-side per verzoek; de URL is geen sleutel |
| rol-kanaal | geen upload waar geen antwoordveld staat — één voorwaarde, `kan_antwoorden()` |

**Twee vragen terug:**
1. Het leesgat op `/file` (48 bestanden, ook privé-projecten): in dezelfde beurt dichten of apart?
2. Office-bestanden (docx/xlsx/pptx) in de allowlist, of eerst alleen afbeelding + pdf + tekst?
