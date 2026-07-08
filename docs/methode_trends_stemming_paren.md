# Methode — Trends stemming-paren

De herbruikbare werkwijze voor de `trends`-bron (stemming-paren). **De termenlijst zelf staat niet hier
maar in de meetcatalogus** (`docs/meetcatalogus.md`, blok `trends`); dit document beschrijft *hoe* je een
kandidaat-paar valideert en waarom de methode zo is.

---

## Waarom paren, geen losse termen

- Google Trends normaliseert **per request op de zwaarste term** (schaal 0-100). Een **losse term**, of
  een term tegen een **dominant anker**, comprimeert daardoor alles kleins naar 0-1 — het signaal
  verdwijnt in de ruis. Bewezen op 2026-07-08: de Library-conversietermen, `barefoot ÷ shoes` en
  `minimalism ÷ shopping` scoorden allemaal 0-1 tegen de dominante term.
- **Twee termen van vergelijkbare grootte tegen elkaar** (ratio A/B) meet de **verschuiving tussen twee
  stemmingen** zónder dominantieprobleem. Beide termen delen dezelfde 0-100-normalisatie binnen één
  request, dus de ratio is stabiel. **De ratio zelf is het signaal:** stijgt hij, dan wint kant A.

## De poort (elke kandidaat MOET hierdoor vóór hij de config in gaat)

1. **Volume.** Beide termen: **mean ≥ 5** op de 0-100-schaal én **≥ 90% van de weekpunten niet-nul**, over
   **5 jaar** (`timeframe="today 5-y"`, geo worldwide). Geen van beide termen mag de ander verpletteren
   (anders is het weer een dominantie-/compressieprobleem, geen echte ratio).
2. **Semantiek.** Controleer de **top-5 related queries per term** (pytrends `related_queries`). Meet de
   term wat we bedoelen? Voorbeelden van de valkuil: *fossil* → fossiele **brandstof** of het **merk
   Fossil** (horloges) i.p.v. materiaal; *citizens* → **burgerschap** of **Citizens Bank**; *consumers* →
   het frame of **Consumers Energy/Credit**. **Off-target related queries = AFGEWEZEN, óók bij genoeg
   volume.** Geen related queries = zuiverheid niet te bevestigen = afgewezen.
3. **Read-only dry-run levert de tabel** (`paar | mean A | mean B | %niet-nul A/B | top related A/B |
   oordeel`); **Stefan stempelt** de definitieve set. Alleen paren die BEIDE checks halen komen in
   aanmerking.

## Ontwerpregels (vastgelegd — niet per keer heroverwegen)

- **Oriëntatie vast.** **A = de kant waarvan stijging "interessant" is** (zuinigheid / behoud /
  nieuw-materiaal), **B = de tegenpool**. De ratio A/B stijgt = kant A wint. **Een bestaand paar omdraaien
  breekt de reeks** (de historische waarden keren om) — doe dat nooit stilzwijgend.
- **Complete-week-label** (zondag-grens): de lopende, onvolledige week (Trends `isPartial=True`) wordt
  overgeslagen; het label is de laatste complete week. Zie de meetcatalogus-conventies.
- **Nieuwe paren = nieuwe reeksen** naast de bestaande. **Toevoegen breekt niets** (een extra
  `trends_ratio_<A>_<B>_day`-reeks); **wisselen of omdraaien van een bestaand paar wél** — dat is een
  bewuste, aparte scope.

## Geschiedenis (waarom deze methode ontstond)

De methode is het resultaat van twee poort-iteraties op **2026-07-08** (zie
`docs/trends_sentiment_termset_meting_2026-07-08.md`):

- **Iteratie 1 — anker-ratio tegen "shoes":** faalde **0/5**. Elke niche comprimeerde naar 0-1 tegen de
  dominante term "shoes" — precies het normalisatie-/compressieprobleem hierboven.
- **Iteratie 2 — paren van vergelijkbare grootte:** slaagde **3/5** (`thrift÷luxury`,
  `second hand÷brand new`, `repair÷replace`) met 100% niet-nul over 5 jaar.

Dat contrast (0/5 los-tegen-anker vs. 3/5 paren) is het bewijs onder deze methode. Iteratie 3 (kandidaat-
paren + semantiekcheck) voegde de related-queries-poort toe als vaste tweede eis.
