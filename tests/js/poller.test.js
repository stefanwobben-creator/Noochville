/* De generieke poller uit `nooch.js`, ECHT gedraaid — niet op zijn brontekst getoetst.
 *
 * WAAROM DIT BESTAND BESTAAT. De JS in dit dorp wordt tot nu toe getoetst door op strings in de
 * bron te asserten (`tests/test_bezig_indicator.py`). Dat vangt een verwijderde regel, maar het
 * bewijst geen gedrag: de bug die hier gefixt wordt — het Topic-veld dat tijdens het typen werd
 * overschreven — zou elke bron-assert hebben overleefd, want de regel die hem veroorzaakte
 * (`el.innerHTML = html`) is precies de regel die er hoort te staan.
 *
 * WAT HIER GEBEURT. Een minimale DOM-stub, daarna wordt het ECHTE `nooch.js` geladen en de poller
 * met de hand aangetikt. Geen jsdom: die staat niet in dit project en één klok + één element is
 * alles wat de poller aanraakt. De stub is expres dom — wat hij niet kan, gebruikt de poller niet.
 *
 * Draait via `tests/test_nooch_js_poller.py` (of met de hand: `node tests/js/poller.test.js`).
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

/* ── De stub ──────────────────────────────────────────────────────────────────────────────── */

function maakVeld(tag, type) {
  return {
    tagName: tag,
    isContentEditable: false,
    _type: type,
    getAttribute(n) { return n === "type" ? this._type : null; },
  };
}

function maakOmgeving(html) {
  const el = {
    dataset: {},
    innerHTML: html,
    _kinderen: [],
    getAttribute(n) {
      if (n === "data-poll") return "/linkbuilding-status";
      if (n === "data-poll-ms") return "5000";
      return null;
    },
    contains(node) { return this._kinderen.indexOf(node) !== -1; },
  };

  const klok = [];                       // geplande tikken: [{ms, fn}]
  const omgeving = {
    el,
    klok,
    antwoord: "<p>vers</p>",             // wat de server teruggeeft
    fetches: 0,
    tik() {                              // voer de eerstvolgende geplande tik uit
      const t = klok.shift();
      if (!t) throw new Error("er stond geen tik gepland");
      t.fn();
      return new Promise((r) => setImmediate(() => setImmediate(r)));   // fetch-ketting afwikkelen
    },
  };

  global.window = { NV: undefined };
  global.location = { search: "" };          // `feest()` leest de querystring bij het bedraden
  global.document = {
    readyState: "complete",
    hidden: false,
    activeElement: null,
    addEventListener() {},
    getElementById() { return null; },
    querySelector() { return null; },
    createElement() { return { innerHTML: "", querySelectorAll: () => [] }; },
    querySelectorAll(sel) { return sel === "[data-poll]" ? [el] : []; },
  };
  global.setTimeout = (fn, ms) => { klok.push({ ms, fn }); return klok.length; };
  global.clearTimeout = () => {};
  global.fetch = () => {
    omgeving.fetches++;
    return Promise.resolve({ ok: true, text: () => Promise.resolve(omgeving.antwoord) });
  };
  return omgeving;
}

function start(html) {
  const omg = maakOmgeving(html);
  delete require.cache[BRON];
  new Function(fs.readFileSync(BRON, "utf8"))();     // het echte bestand, in deze stub-wereld
  return omg;
}

/* ── De toetsen ───────────────────────────────────────────────────────────────────────────── */

(async function () {
  console.log("1. zonder focus vervangt de poller gewoon");
  {
    const omg = start("<p>oud</p>");
    await omg.tik();
    check("het fragment is vervangen", omg.el.innerHTML === "<p>vers</p>");
    check("er staat een volgende tik gepland", omg.klok.length === 1);
  }

  console.log("2. TYPEN IN HET FRAGMENT BLIJFT STAAN (de bug van 28 september)");
  {
    const omg = start("<form><input id='lb-topic'></form>");
    const veld = maakVeld("INPUT", "text");
    omg.el._kinderen.push(veld);
    global.document.activeElement = veld;
    const voor = omg.el.innerHTML;
    await omg.tik();
    check("het fragment is NIET vervangen", omg.el.innerHTML === voor);
    check("de server is wél bevraagd (geen stilstand)", omg.fetches === 1);
    check("en de volgende ronde staat gepland", omg.klok.length === 1);

    // Cursor weg → de eerstvolgende ronde haalt de achterstand in.
    global.document.activeElement = null;
    await omg.tik();
    check("na het verlaten van het veld vervangt hij alsnog", omg.el.innerHTML === "<p>vers</p>");
  }

  console.log("3. een textarea telt mee, een knop niet");
  {
    const omg = start("<p>oud</p>");
    const ta = maakVeld("TEXTAREA", null);
    omg.el._kinderen.push(ta);
    global.document.activeElement = ta;
    await omg.tik();
    check("textarea blokkeert de vervanging", omg.el.innerHTML === "<p>oud</p>");

    // EEN KLIK OP PITCH/IGNORE MAG NIET BLOKKEREN: na de klik is de knop het actieve element, en
    // juist dán moet het paneel bijwerken. "Er is iets gefocust" was dus de verkeerde toets.
    const knop = maakVeld("BUTTON", null);
    omg.el._kinderen.push(knop);
    global.document.activeElement = knop;
    await omg.tik();
    check("een knop met focus blokkeert niet", omg.el.innerHTML === "<p>vers</p>");
  }

  console.log("4. focus BUITEN het fragment gaat de poller niet aan");
  {
    const omg = start("<p>oud</p>");
    global.document.activeElement = maakVeld("INPUT", "text");   // niet in `_kinderen`
    await omg.tik();
    check("een zoekveld elders op de pagina blokkeert niets",
          omg.el.innerHTML === "<p>vers</p>");
  }

  console.log(fouten ? `\n${fouten} toets(en) FOUT` : "\nalles groen");
  process.exit(fouten ? 1 : 0);
})();
