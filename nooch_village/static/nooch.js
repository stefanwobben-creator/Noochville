/* NoochVille — de gedeelde fragment-mechaniek.
 *
 * Eén plek voor de klasse fouten die drie keer op rij op drie schermen opdook: een stuk pagina dat
 * zichzelf vervangt. Wat er dan mis gaat is elke keer hetzelfde, en dus hoort de oplossing één keer
 * te bestaan in plaats van per scherm opnieuw:
 *
 *   1. het veld waarin je aan het typen bent wordt vervangen  → toetsaanslagen weg
 *   2. de verse formulieren zijn niet bedraad                 → ze posten gewoon en navigeren je weg
 *   3. bedraden gebeurt tweemaal op hetzelfde formulier       → elke actie post dubbel
 *   4. een teller elders op het scherm blijft op zijn oude waarde staan
 *
 * Twee dingen, allebei data-gestuurd, zodat een VOLGEND scherm ze krijgt door attributen te zetten
 * en niet door dit bestand te kopiëren:
 *
 *   NV.swap(doel, url)   vervangt een fragment: haalt op, plakt, bedraadt opnieuw, spiegelt de
 *                        tellers en zet je cursor terug waar hij stond. `doel` mag ontbreken —
 *                        dan wordt het fragment alleen gelezen (voor de tellers), niet getoond.
 *
 *   form[data-qa-frag]   een "typ-en-Enter"-formulier: de inzendingen gaan door een wachtrij zodat
 *                        drie regels achter elkaar alle drie landen, en het veld zelf wordt NOOIT
 *                        vervangen — alleen leeggemaakt. Na de laatste inzending één swap.
 *
 * Attributen op zo'n formulier:
 *   data-qa-frag     URL van het fragment dat ná het opslaan de waarheid is
 *   data-qa-action   de dispatch-actie (die zit normaal op de knop, en `new FormData` neemt
 *                    knopwaarden niet mee — precies de stille no-op van eerder)
 *   data-qa-target   CSS-selector van het element dat vervangen wordt (mag ontbreken)
 *   data-qa-input    op het invoerveld zelf
 *
 * Tellers: een element IN het fragment met `data-nv-mirror="<selector>"` kopieert zijn tekst naar
 * dat element op de pagina. Zo blijft de tekst (enkelvoud/meervoud, taal) server-side waar hij
 * hoort, en werkt de teller ook als het fragment zelf niet op het scherm staat.
 */
(function () {
  var NV = (window.NV = window.NV || {});

  function mirror(root) {
    root.querySelectorAll("[data-nv-mirror]").forEach(function (src) {
      var doel = document.querySelector(src.getAttribute("data-nv-mirror"));
      if (doel) doel.textContent = src.textContent;
    });
    // Sommige plekken zijn geen getal maar een blokje opmaak — de puntenlijst genest onder de
    // Agenda-stap bijvoorbeeld. De bron is ons eigen server-fragment, dus geen vreemde markup.
    root.querySelectorAll("[data-nv-mirror-html]").forEach(function (src) {
      var doel = document.querySelector(src.getAttribute("data-nv-mirror-html"));
      if (!doel) return;
      doel.innerHTML = src.innerHTML;
      // Verse links in het menu moeten weer door de modal-controller: anders navigeert een klik
      // de overlay uit in plaats van de stap te openen.
      if (window.__ovlWireLinks) window.__ovlWireLinks(doel);
    });
  }

  // Cursor + tekst van het veld waarin je stond. Zonder dit verliest elke swap je halve zin.
  function bewaarFocus(box) {
    var a = document.activeElement;
    if (!box || !a || !a.id || !box.contains(a)) return null;
    try {
      return { id: a.id, v: a.value, s: a.selectionStart, e: a.selectionEnd };
    } catch (err) {
      return { id: a.id, v: a.value, s: null, e: null };
    }
  }

  function herstelFocus(k) {
    if (!k) return;
    var n = document.getElementById(k.id);
    if (!n) return;
    n.value = k.v;
    n.focus();
    if (k.s !== null) {
      try { n.setSelectionRange(k.s, k.e); } catch (err) {}
    }
  }

  NV.swap = function (doel, url) {
    var box = typeof doel === "string" ? document.querySelector(doel) : doel || null;
    return fetch(url, { credentials: "same-origin" })
      .then(function (r) { return r.text(); })
      .then(function (h) {
        var keep = bewaarFocus(box);
        var houder = box || document.createElement("div");
        houder.innerHTML = h;
        mirror(houder);
        if (!box) return houder;                 // alleen gelezen: niets te bedraden
        NV.wire(box);
        // De modal heeft zijn eigen formulier-afhandeling (fetch + overlay verversen). Staat hij
        // open, dan moeten de verse rijen daar ook doorheen — anders posten ze de overlay uit.
        if (window.__ovlWireForms) window.__ovlWireForms(box);
        herstelFocus(keep);
        return houder;
      })
      .catch(function () { return null; });
  };

  function quickAdd(f) {
    if (f.dataset.nvWired) return;
    f.dataset.nvWired = "1";
    var inp = f.querySelector("[data-qa-input]");
    if (!inp) return;
    var wacht = [], bezig = false;

    function stuur(tekst) {
      var d = new URLSearchParams(new FormData(f));
      d.set(inp.name, tekst);
      d.set("action", f.dataset.qaAction || "");
      return fetch("/action", { method: "POST", body: d, credentials: "same-origin" });
    }

    function volgende() {
      if (bezig || !wacht.length) return;
      bezig = true;
      stuur(wacht.shift())
        .then(function () {
          bezig = false;
          volgende();
          if (!wacht.length) NV.swap(f.dataset.qaTarget || null, f.dataset.qaFrag);
        })
        .catch(function () { bezig = false; f.submit(); });   // netwerk weg: laat de browser het doen
    }

    f.addEventListener("submit", function (e) {
      var t = inp.value.trim();
      if (!t) { e.preventDefault(); return; }
      e.preventDefault();
      inp.value = "";
      inp.focus();                                  // veld meteen vrij voor het volgende punt
      wacht.push(t);
      volgende();
    });
  }

  // ── Inline bewerken (fase 10 punt 4) ──────────────────────────────────────────────────────
  // Drie kleine dingen, en bewust niet meer dan dat:
  //   1. klikken op de tekst opent het bewerk-formulier eronder;
  //   2. de opslaan-balk verschijnt pas als er echt iets is getypt;
  //   3. annuleren klapt dicht en zet de velden terug.
  // Er wordt NIETS opgeslagen vanuit deze code: het blijft hetzelfde formulier met dezelfde ene
  // submit naar `artefact_edit`. Zonder JS werkt alles nog: de "edit"-summary opent de <details>
  // en de balk is dan gewoon zichtbaar (zie de `hidden`-reset hieronder).
  function inlineEdit(root) {
    root.querySelectorAll("[data-qadd-open]").forEach(function (el) {
      if (el.dataset.nvWired) return;
      el.dataset.nvWired = "1";
      el.addEventListener("click", function (e) {
        if (e.target.closest("a, button, input, textarea")) return;   // een link blijft een link
        var kaart = el.closest(".c2-main") || document;
        var det = kaart.querySelector("details[data-qadd-inline]");
        if (det) { det.open = true; var f = det.querySelector("textarea, input[name=title]"); if (f) f.focus(); }
      });
    });
    root.querySelectorAll("form[data-qadd-dirty]").forEach(function (f) {
      if (f.dataset.nvWired) return;
      f.dataset.nvWired = "1";
      var bar = f.querySelector(".qadd-bar");
      if (!bar) return;
      var schoon = new FormData(f);
      function vuil() {
        var nu = new FormData(f);
        var anders = false;
        nu.forEach(function (v, k) { if (String(schoon.get(k)) !== String(v)) anders = true; });
        bar.hidden = !anders;
      }
      f.addEventListener("input", vuil);
      f.addEventListener("change", vuil);
      var x = f.querySelector("[data-qadd-cancel]");
      if (x) x.addEventListener("click", function () {
        f.reset(); bar.hidden = true;
        var det = f.closest("details"); if (det) det.open = false;
      });
    });
  }

  // Zonder JS zou de opslaan-knop onbereikbaar zijn, want `hidden` staat in de HTML. Deze regel
  // draait die volgorde om: de balk is verborgen ZODRA de JS draait, en anders gewoon zichtbaar.
  function barReset(root) {
    root.querySelectorAll("form[data-qadd-dirty] .qadd-bar").forEach(function (b) { b.hidden = true; });
  }

  // Idempotent: `data-nv-wired` per formulier, zodat een fragment dat opnieuw langskomt geen
  // tweede listener krijgt. Een dubbele listener post elke actie twee keer.
  NV.wire = function (root) {
    root = root || document;
    root.querySelectorAll("form[data-qa-frag]").forEach(quickAdd);
    barReset(root);
    inlineEdit(root);
  };

  if (document.readyState !== "loading") NV.wire(document);
  else document.addEventListener("DOMContentLoaded", function () { NV.wire(document); });
})();
