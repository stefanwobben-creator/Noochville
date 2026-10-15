/* `#vraag-<k>` opent het dichtgeklapte vragenblok (W1b, 15 oktober 2026), ECHT gedraaid op het
 * echte `nooch.js` met een minimale DOM-stub. Twee wegen: een DIRECTE URL (de hash staat er al bij
 * het laden; `NV.wire(document)` draait) en een klik op dezelfde pagina (`hashchange`).
 * Draait via `tests/test_w1b_inklappen.py` (of `node tests/js/vraag_anker.test.js`). */
"use strict";
const fs = require("fs");
const path = require("path");
let fouten = 0;
function check(naam, waar) { console.log((waar ? "  ok   " : "  FOUT ") + naam); if (!waar) fouten++; }

function dorp(hash) {
  const details = { open: false, tagName: "DETAILS" };
  const gescrold = [];
  const vraag = { id: "vraag-plastic", closest: (s) => (s === "details" ? details : null),
                  scrollIntoView: () => gescrold.push("vraag-plastic") };
  const luisteraars = {};
  global.window = { NV: undefined, location: { hash, search: "" },
                    addEventListener: (n, f) => { (luisteraars[n] = luisteraars[n] || []).push(f); } };
  global.location = global.window.location;
  global.document = {
    readyState: "complete", addEventListener() {}, querySelector() { return null; },
    querySelectorAll() { return []; },
    getElementById: (id) => (id === "vraag-plastic" ? vraag : null),
  };
  new Function(fs.readFileSync(path.join(__dirname, "..", "..", "nooch_village", "static", "nooch.js"), "utf8"))();
  return { details, gescrold, luisteraars };
}

// 1. directe URL: bij het laden staat de hash er al
let d = dorp("#vraag-plastic");
check("directe URL: het blok gaat open", d.details.open === true);
check("directe URL: er wordt naar de vraag gescrold", d.gescrold.includes("vraag-plastic"));

// 2. klik op dezelfde pagina: eerst geen hash, dan hashchange
d = dorp("");
check("zonder hash blijft het blok dicht", d.details.open === false);
global.window.location.hash = "#vraag-plastic";
(d.luisteraars.hashchange || []).forEach((f) => f());
check("hashchange: het blok gaat open en scrolt", d.details.open === true && d.gescrold.length === 1);

// 3. een ander anker of een onbekende vraag doet niets
d = dorp("#vraag-bestaat-niet");
check("onbekende vraag: niets open", d.details.open === false && d.gescrold.length === 0);
d = dorp("#m-123");
check("ander anker: niets", global.window.NV.vraagAnker(global.document) === false);
process.exit(fouten ? 1 : 0);
