/* De bulk-import-parser uit `nooch.js` (NV.bulkParse), ECHT gedraaid. Draait via
 * `tests/test_w1_bulk_import.py` (of met de hand: `node tests/js/bulk_import.test.js`). */
"use strict";
const fs = require("fs");
const path = require("path");
let fouten = 0;
function check(naam, waar) { console.log((waar ? "  ok   " : "  FOUT ") + naam); if (!waar) fouten++; }
global.window = { NV: undefined };
global.location = { search: "" };
global.document = { readyState: "loading", addEventListener() {}, querySelector() { return null; },
                    querySelectorAll() { return []; } };
new Function(fs.readFileSync(path.join(__dirname, "..", "..", "nooch_village", "static", "nooch.js"), "utf8"))();
const parse = global.window.NV.bulkParse;

// DE FOUT: een `##`-kop zette alles in de markdown-stand. Dit is de vorm van de zes kapotte feiten.
const geplakt = "## Location & contact\nText: LTA runs its plant at Via Bologna 230\nType: link\n" +
  "Ref: LTA S.r.l. contact page\nQuote: Via Bologna 230/250\nURL: https://lta.example/contact\n\n" +
  "## Company certification\nText: LTA holds EMAS registration IT-001529\nType: source\nRef: EMAS register";
const r = parse(geplakt);
check("twee feiten, niet één per sectie-blob", r.length === 2);
check("Text bevat geen veldnamen", !/\b(Type|Ref|Quote|URL)\s*:/.test(r[0].Text));
check("Type, Ref, Quote, URL los", r[0].Type === "link" && r[0].Ref === "LTA S.r.l. contact page" &&
      r[0].Quote === "Via Bologna 230/250" && r[0].URL === "https://lta.example/contact");
check("de kop wordt For", r[0].For === "Location & contact" && r[1].For === "Company certification");
check("een eigen For wint van de kop", parse("## A\nText: x\nFor: B")[0].For === "B");
check("zonder kop: zoals altijd", JSON.stringify(parse("Text: y\nType: source")) === JSON.stringify([{Text: "y", Type: "source"}]));
check("echte vrije markdown blijft markdown", parse("## Notes\nSome narrative.")[0].Type === "source");
process.exit(fouten ? 1 : 0);
