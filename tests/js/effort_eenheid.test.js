/* `NV.effortEenheid` uit `nooch.js`, ECHT gedraaid — zelfde harnas-vorm als `poller.test.js`.
 *
 * DE BUG. De Effort-select postte bij een wissel het formulier zoals het stond: "5" + "dagen" →
 * "uren" kiezen stuurde `5 uren`, en een project van 40 uur stond daarna op 5. Deze toetsen kijken
 * naar wat er VERSTUURD wordt, want dat getal is wat `uren_uit` op de server opslaat.
 *
 * Draait via `tests/test_effort_eenheid.py` (of met de hand: `node tests/js/effort_eenheid.test.js`).
 */
"use strict";
const fs = require("fs");
const path = require("path");

const BRON = path.join(__dirname, "..", "..", "nooch_village", "static", "nooch.js");

let fouten = 0;
function check(naam, waar) {
  console.log((waar ? "  ok   " : "  FOUT ") + naam);
  if (!waar) fouten++;
}

global.window = { NV: undefined };
global.location = { search: "" };
global.document = {
  readyState: "loading",                     // niet bedraden: alleen de functie is hier nodig
  addEventListener() {},
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
new Function(fs.readFileSync(BRON, "utf8"))();
const NV = global.window.NV;

/* Eén Effort-formulier: getalveld + select met `data-unit`, zoals `_effort_control` ze rendert. */
function wissel(getal, van, naar) {
  const attrs = { "data-unit": van };
  const veld = { value: getal };
  const uit = { verstuurd: null };
  const form = {
    querySelector(sel) { return sel === "input[name=number]" ? veld : null; },
    requestSubmit() { uit.verstuurd = veld.value === "" ? "" : String(veld.value); },
  };
  const sel = {
    form, value: naar,
    getAttribute(n) { return attrs[n]; },
    setAttribute(n, v) { attrs[n] = v; },
  };
  NV.effortEenheid(sel);
  uit.dataUnit = attrs["data-unit"];
  return uit;
}

let r = wissel("5", "dagen", "uren");
check("5 dagen → uren verstuurt 40, niet 5", r.verstuurd === "40");
check("data-unit volgt de nieuwe eenheid", r.dataUnit === "uren");
check("40 uren → dagen verstuurt 5", wissel("40", "uren", "dagen").verstuurd === "5");
check("2 dagen → uren verstuurt 16", wissel("2", "dagen", "uren").verstuurd === "16");
// Niet afronden naar 0: `uren_uit` maakt van 0 een None, en dan is de schatting weg.
check("3 uren → dagen verstuurt 0.375 (= 3 uur), geen 0", wissel("3", "uren", "dagen").verstuurd === "0.375");
// Leeg veld: NIET versturen. Een lege post is voor de server "wissen", en de render van een lege
// schatting valt terug op "uren" — de gekozen eenheid sprong dan terug.
r = wissel("", "uren", "dagen");
check("leeg veld verstuurt niets", r.verstuurd === null);
check("leeg veld houdt de gekozen eenheid vast in data-unit", r.dataUnit === "dagen");
check("onzin in het veld verstuurt ook niets", wissel("abc", "uren", "dagen").verstuurd === null);
check("komma als decimaalteken: 1,5 dagen → 12", wissel("1,5", "dagen", "uren").verstuurd === "12");
check("zelfde eenheid laat het getal staan", wissel("5", "uren", "uren").verstuurd === "5");

process.exit(fouten ? 1 : 0);
