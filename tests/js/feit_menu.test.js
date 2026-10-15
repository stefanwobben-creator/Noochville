/* Het ⋯-menu en de bronpoort van "+ Add fact" (nooch.js, 15 oktober 2026), echt gedraaid.
 * Escape sluit een open <details data-esc> en zet de focus op de summary; het vinkje "I checked
 * this" staat pas aan als er een link, een bestand of "first-hand" is. */
"use strict";
const fs = require("fs");
const path = require("path");
let fouten = 0;
function check(naam, waar) { console.log((waar ? "  ok   " : "  FOUT ") + naam); if (!waar) fouten++; }
global.window = { NV: undefined, location: { hash: "", search: "" } };
global.location = global.window.location;
global.document = { readyState: "loading", addEventListener() {}, querySelector() { return null; },
                    querySelectorAll() { return []; }, getElementById() { return null; } };
new Function(fs.readFileSync(path.join(__dirname, "..", "..", "nooch_village", "static", "nooch.js"), "utf8"))();
const NV = global.window.NV;

// Escape
let gefocust = false;
const summary = { focus() { gefocust = true; } };
const menu = { open: true, querySelector: () => summary };
const knop = { closest: (s) => (s === "details[data-esc][open]" ? menu : null) };
let voorkomen = false;
check("Escape in een open menu sluit het", NV.escSluit({ key: "Escape", target: knop, preventDefault() { voorkomen = true; } }) === true);
check("… en het menu is dicht met de focus op ⋯", menu.open === false && gefocust && voorkomen);
check("een andere toets doet niets", NV.escSluit({ key: "Enter", target: knop }) === false);
check("Escape buiten een menu doet niets", NV.escSluit({ key: "Escape", target: { closest: () => null } }) === false);

// bronpoort
function form(soort, url, bestanden) {
  const vink = { disabled: true, checked: true };
  const velden = { soort: { value: soort }, url: { value: url }, file: { files: bestanden }, nakijken: vink };
  return { vink, querySelector: (s) => velden[s.match(/name=(\w+)/)[1]] };
}
let f = form("bron", "", []);
check("zonder bron: vinkje uit en niet aangevinkt", NV.bronPoort(f) === false && f.vink.disabled && !f.vink.checked);
f = form("bron", "https://x", []);
check("met een link: vinkje aan", NV.bronPoort(f) === true && !f.vink.disabled);
f = form("document", "", [{ name: "a.pdf" }]);
check("met een bestand: vinkje aan", NV.bronPoort(f) === true && !f.vink.disabled);
f = form("attested", "", []);
check("first-hand: vinkje aan", NV.bronPoort(f) === true && !f.vink.disabled);
process.exit(fouten ? 1 : 0);
