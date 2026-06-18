# NoochVille: Skill-spec — `keywords_everywhere` (rol: scout) — 2026-06-18

*Spec-first contract, geen implementatie. Dit is het vastgepinde doelwit dat Claude Code letterlijk volgt, zodat de review in één of twee rondes klopt in plaats van zes. Bouw niets buiten dit contract zonder eerst hier een regel te wijzigen. Respecteer de spelregels: skills falen closed (HARDE REGEL 5), capaciteit is mens-gated (HARDE REGEL 10), per-edit review vóór commit.*

---

## 1. Mandaat-fit

Scout's purpose is kansen vinden in zoekdata en de woordenschat voeden. Deze skill verrijkt kandidaat-keywords met echte search volume, CPC, competitie en een 12-maands trend. Mandaat aanwezig, nieuw middel: schone A-case, toekenning via `amend_role(add_skills=[...])` op `scout`.

## 2. Capability

- `name = "keywords_everywhere"`
- `needs_secret = True`
- `description = "Haalt echte search volume, CPC, competitie en 12-maands trend per keyword uit de Keywords Everywhere API (geen mock)."`
- file: `nooch_village/skills_impl/keywords_everywhere.py`, class `KeywordsEverywhereSkill`
- registreren: `village.py` → `self.registry.register(KeywordsEverywhereSkill())`
- toekennen: `amend_role` op `scout`, `add_skills=["keywords_everywhere"]`, proposer `human-cli`, via `Village.submit_proposal` → gate → Secretary adopt

## 3. Secret (.env)

- `KEYWORDS_EVERYWHERE_API_KEY`, gelezen via `context.settings.get("KEYWORDS_EVERYWHERE_API_KEY") or os.getenv("KEYWORDS_EVERYWHERE_API_KEY")` (zelfde patroon als `plausible.py`).
- Ontbreekt → `raise RuntimeError(...)`. Fail-closed, nooit mock.

## 4. Bron-API (geverifieerd, niet verzonnen)

- `POST https://api.keywordseverywhere.com/v1/get_keyword_data`
- Headers: `Authorization: Bearer <key>`, `Accept: application/json`
- Body (form-encoded): `dataSource`, `country`, `currency`, en herhaalde `kw[]=...`
- Max 100 keywords per request, 1 credit per teruggegeven keyword
- Response:

```json
{ "data": [ { "keyword": "digital marketing", "vol": 90500,
              "cpc": { "currency": "$", "value": "9.96" },
              "competition": 0.62,
              "trend": [ { "month": "January", "year": 2026, "value": 110000 } ] } ],
  "credits": 148520, "credits_consumed": 1, "time": 0.31 }
```

## 5. Input (payload)

| veld | type | default | regel |
|------|------|---------|-------|
| `kw` | `list[str]` | (verplicht) | 1 tot 100. Leeg → `raise ValueError`. >100 → `raise ValueError` (caller batcht zelf, geen stille truncatie). |
| `country` | `str` | `"nl"` | overrulebaar per call |
| `currency` | `str` | `"eur"` | overrulebaar per call |
| `data_source` | `str` | `"gkp"` | `"gkp"` = Google Keyword Planner (default, reproduceerbaar). `"cli"` = clickstream-blend, opt-in voor long-tail. Andere waarde → `raise ValueError`. |

## 6. Output (genormaliseerd — dit is de testbare contractvorm)

```python
{ "source": "keywords_everywhere",
  "country": "nl", "currency": "eur", "data_source": "gkp",
  "credits_consumed": 17, "credits_remaining": 148520,
  "keywords": [
    { "keyword": "...", "vol": 90500, "cpc": 9.96, "competition": 0.62,
      "trend": [ { "month": "January", "year": 2026, "value": 110000 } ] } ] }
```

Normalisatie-regels (pin, anders fragiele tests):
- `cpc` wordt een `float` uit `cpc.value`; de currency staat top-level, niet per keyword.
- `vol` blijft `int`, `competition` blijft `float`, `trend` blijft de ruwe lijst.
- `credits` uit de response wordt `credits_remaining`; `credits_consumed` blijft.

## 7. Fail-closed gedrag

- Geen API-key → `raise RuntimeError`.
- Lege `kw` → `raise ValueError`. >100 `kw` → `raise ValueError`. Onbekende `data_source` → `raise ValueError`.
- HTTP 4xx/5xx → `raise_for_status()`. Anders dan bij `plausible` (waar breakdowns verrijking zijn) is de keyword-data hier het hele doel: een fout mag NOOIT stil als lege output terugkomen.
- Credit-uitputting geeft een API-fout: surface die expliciet (raise met de boodschap), nooit lege output verzinnen.

## 8. Het addertje: dit kost echt credits

Eén credit per teruggegeven keyword, dus 100 keywords = 100 credits = echt geld. Harde gebruiksregel, onderdeel van het contract:

- **Deze skill mag nooit in de dagpuls hangen.** Hij is on-demand, voor een gecureerde shortlist (een discovery-project of een door scout voorgestelde batch), niet de hele woordenschat. Dit is het "scope-first, geen overproductie"-principe uit de projecten-notitie, toegepast op data die geld kost.
- De skill geeft `credits_remaining` terug zodat de burn zichtbaar is in de Field Note en de cockpit.

## 9. Golden fixtures + tests

- `tests/fixtures/keywords_everywhere/get_keyword_data.json`: het docs-voorbeeld als vastgelegde response.
- `tests/test_keywords_everywhere.py`, `requests.post` gemockt (geen echte call in de suite):
  1. `test_normalizes_response`: fixture → exacte verwachte output-dict (cpc als float, credits_remaining gevuld).
  2. `test_no_key_fails_closed`: geen env-key → `RuntimeError`.
  3. `test_http_error_raises`: `raise_for_status` gemockt om te gooien → propageert.
  4. `test_too_many_keywords_raises`: 101 kw → `ValueError`, geen call gedaan.
  5. `test_empty_keywords_raises`: lege lijst → `ValueError`.
  6. `test_unknown_data_source_raises`: `data_source="xyz"` → `ValueError`.

## 10. Granting op scout (de makkelijke helft)

`amend_role` op `scout`, `add_skills=["keywords_everywhere"]`, proposer `human-cli`, via de gate. Tension/rationale: scout heeft het mandaat (keyword-kansen vinden, woordenschat voeden) en mist het middel om volume/CPC/competitie op te halen. Pas dit toe nádat de skill in de registry staat (anders sneuvelt het op `test_record_registry_consistentie`).

## 11. Roadmap (bewust niet in v1)

- **Batchen >100**: v1 raised. Later kan de skill of een aanroepende laag in stukken van 100 hakken, mits de credit-kost zichtbaar en begrensd blijft (geen verborgen meervoudige calls). Bewust uitstellen tot er een echte behoefte is.
- **Andere endpoints** (`get_related_keywords`, `get_pasf_keywords`, `get_domain_keywords`): aparte skills op dezelfde key/plumbing, niet deze skill oprekken.
- **MCP-server** (`mcp.keywordseverywhere.com/mcp`): handig om de API te bevoelen vanuit Claude Code, maar geen skill in het dorp. NoochVille's patroon is een echte Skill in de registry, mens-gated toegekend.

## 12. Genomen beslissingen (vastgepind)

1. `currency = "eur"`, `country = "nl"` (beide overrulebaar per call).
2. >100 keywords → `raise` in v1; batchen op de roadmap.
3. `data_source` default `"gkp"`; `"cli"` (clickstream) als opt-in param.
