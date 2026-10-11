/* De rekenhulpen van de Finance-formulieren uit `nooch.js`, ECHT gedraaid — zelfde harnas als
 * `effort_eenheid.test.js`. Draait via `tests/test_finance_formulieren.py`. */
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
global.document = { readyState: "loading", addEventListener() {}, querySelector() { return null; },
                    querySelectorAll() { return []; } };
new Function(fs.readFileSync(BRON, "utf8"))();
const NV = global.window.NV;

function reken(totaal, tarief) {
  const r = NV.finBtw(NV.finCent(totaal), tarief);
  return [NV.finEuro(r[0]), NV.finEuro(r[1])];
}
check("121,00 met 21% → 100,00 en 21,00", JSON.stringify(reken("121,00", 21)) === '["100,00","21,00"]');
check("109,00 met 9% → 100,00 en 9,00", JSON.stringify(reken("109,00", 9)) === '["100,00","9,00"]');
check("50,00 met 0% → 50,00 en 0,00", JSON.stringify(reken("50,00", 0)) === '["50,00","0,00"]');
check("1.234,56 wordt 123456 cent", NV.finCent("1.234,56") === 123456);
check("1,234.56 wordt 123456 cent", NV.finCent("1,234.56") === 123456);
check("€ 12 wordt 1200 cent", NV.finCent("€ 12") === 1200);
check("drie decimalen is geen bedrag", NV.finCent("1,234") === null);
check("1234567 cent toont 12.345,67", NV.finEuro(1234567) === "12.345,67");
// GEEN AFRONDINGSFOUTEN: excl + btw is altijd precies het totaal, en altijd hele centen.
let heel = true;
for (const tarief of [21, 9, 0]) {
  for (let c = 1; c <= 50000; c += 7) {
    const r = NV.finBtw(c, tarief);
    if (r[0] + r[1] !== c || !Number.isInteger(r[0]) || !Number.isInteger(r[1])) heel = false;
  }
}
check("excl + btw = totaal, in hele centen, voor 21%, 9% en 0%", heel);
check("samenvatting doorlopend",
      NV.finSamenvatting(45000, "2026-01-01", "") === "€450,00 per month, from 1 January 2026, ongoing.");
check("samenvatting met einddatum",
      NV.finSamenvatting(45000, "2026-01-01", "2026-12-31") ===
      "€450,00 per month, from 1 January 2026, until 31 December 2026.");
check("samenvatting zonder begindatum is leeg", NV.finSamenvatting(45000, "", "") === "");
console.log("JSON " + JSON.stringify([
  NV.finSamenvatting(45000, "2026-01-01", ""), NV.finSamenvatting(123456789, "2026-03-15", "2027-02-28"),
  NV.finSamenvatting(5, "2026-12-31", ""), NV.finSamenvatting(null, "2026-01-01", "")]));
process.exit(fouten ? 1 : 0);
