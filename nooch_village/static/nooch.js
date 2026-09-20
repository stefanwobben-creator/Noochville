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
  /* Het bewerk-formulier openen en er meteen in staan. Twee ingangen, één gedrag:
   *
   *   [data-qadd-open]      de TEKST zelf (klik in de inhoud)
   *   [data-qadd-opener]    een zichtbare knop, bv. "Edit page" bovenaan
   *
   * DE KNOP IS ER BIJGEKOMEN (21 september 2026) omdat de tekst-ingang onvindbaar was: de enige
   * zichtbare aanwijzing was een klein grijs "edit"-linkje ONDER de hele pagina-inhoud. Wie niet
   * wist dat de tekst klikbaar was, vond de bewerkmogelijkheid niet — en dat is precies wat er
   * gebeurde. `scrollIntoView` erbij, want het formulier staat onder een lange pagina: openen
   * zonder ernaartoe gaan is nog steeds onvindbaar. */
  function openBewerken(vanaf) {
    var kaart = vanaf.closest(".c2-main") || document;
    var det = kaart.querySelector("details[data-qadd-inline]");
    if (!det) return;
    det.open = true;
    det.scrollIntoView({ block: "center", behavior: "smooth" });
    var f = det.querySelector("textarea, input[name=title]");
    if (f) f.focus();
  }

  function inlineEdit(root) {
    root.querySelectorAll("[data-qadd-open]").forEach(function (el) {
      if (el.dataset.nvWired) return;
      el.dataset.nvWired = "1";
      el.addEventListener("click", function (e) {
        if (e.target.closest("a, button, input, textarea")) return;   // een link blijft een link
        openBewerken(el);
      });
    });
    root.querySelectorAll("[data-qadd-opener]").forEach(function (el) {
      if (el.dataset.nvWired) return;
      el.dataset.nvWired = "1";
      el.addEventListener("click", function (e) { e.preventDefault(); openBewerken(el); });
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

  // ── Markdown-voorbeeld (fase 10 punt 4b) ──────────────────────────────────────────────────
  // De knop wisselt tussen het tekstvak en de weergave. De weergave komt van de SERVER
  // (`/md-preview` → `_md`), niet van een parser hier: dan toont het voorbeeld per definitie
  // hetzelfde als wat je na opslaan ziet, en is er geen tweede renderer om uit de pas te lopen.
  function mdPreview(root) {
    root.querySelectorAll("[data-md-toggle]").forEach(function (knop) {
      if (knop.dataset.nvWired) return;
      knop.dataset.nvWired = "1";
      knop.addEventListener("click", function () {
        var ed = knop.closest("[data-md-preview]");
        if (!ed) return;
        var ta = ed.querySelector("textarea"), prev = ed.querySelector(".editor-prev");
        if (!ta || !prev) return;
        if (!prev.hidden) { prev.hidden = true; ta.hidden = false; knop.textContent = "👁"; return; }
        var f = knop.closest("form");
        var csrf = f ? (f.querySelector("input[name=csrf]") || {}).value || "" : "";
        var body = new URLSearchParams({ csrf: csrf, tekst: ta.value });
        prev.textContent = "…";
        prev.hidden = false; ta.hidden = true; knop.textContent = "✎";
        fetch("/md-preview", { method: "POST", body: body, credentials: "same-origin",
                               headers: { "Content-Type": "application/x-www-form-urlencoded" } })
          .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
          .then(function (html) { prev.innerHTML = html; })
          // Faalt de call, dan gaat het tekstvak meteen terug open. Een leeg voorbeeldvak zou
          // lezen als "je tekst is weg", en dat is precies het moment waarop iemand gaat plakken.
          .catch(function () { prev.hidden = true; ta.hidden = false; knop.textContent = "👁"; });
      });
    });
  }

  // Zonder JS zou de opslaan-knop onbereikbaar zijn, want `hidden` staat in de HTML. Deze regel
  // draait die volgorde om: de balk is verborgen ZODRA de JS draait, en anders gewoon zichtbaar.
  function barReset(root) {
    root.querySelectorAll("form[data-qadd-dirty] .qadd-bar").forEach(function (b) { b.hidden = true; });
  }

  /* ── Het sleeppatroon op het bord (fase 11, laag 3) ──────────────────────────────────────
   *
   * EIGEN POINTER-IMPLEMENTATIE EN NIET DE NATIVE HTML5-DRAG, en dat is de hele reden dat deze
   * functie bestaat. De native API geeft je één ding niet: zeggenschap over hoe het gesleepte
   * ding eruitziet. `setDragImage` neemt een momentopname en de browser tekent die plat en
   * schaduwloos — dus de hover-lift viel wég op het moment dat je écht ging slepen, precies waar
   * het "optillen" hoorde te beginnen. Stefans woorden: het oppakken mag meer physical affordance.
   *
   * Hier tilt de kaart op en BLIJFT hij opgetild: een kloon volgt de pointer, opgeschaald,
   * gekanteld en met een schaduw eronder (`.pdrag-ghost`), terwijl de plek van herkomst als
   * contour blijft staan (`.pdrag-bron`).
   *
   * ALLEEN MUIS EN PEN. Op touch doet dit niets, met opzet: een sleepgebaar dat scrollen blokkeert
   * maakt een bord op een telefoon onbruikbaar, en de statuswissel heeft daar al een weg (de
   * knop/dropdown op de kaart zelf). Slepen is een versnelling, geen vervanging — dezelfde regel
   * die de toegankelijkheidsval uit de fase-11-spec afdekt.
   *
   * `opties.onDrop(pid, naar)` krijgt de uitkomst; wát er dan gebeurt (formulier posten en
   * herladen op de volle pagina, fetch en verversen in de modal) weet dit bestand niet. Zo staat
   * het gedrag één keer en de afhandeling per scherm.
   */
  var DREMPEL = 5;        // px; hieronder is het een klik en geen sleep

  NV.bord = function (root, opties) {
    root = root || document;
    opties = opties || {};
    if (!opties.onDrop) return;
    root.querySelectorAll(".pcard[data-pid]").forEach(function (kaart) {
      if (kaart.getAttribute("data-nv-sleep")) return;
      kaart.setAttribute("data-nv-sleep", "1");
      // De native vlag uit: anders vecht de browser-drag met deze.
      kaart.setAttribute("draggable", "false");
      kaart.addEventListener("pointerdown", function (e) {
        if (e.button !== 0 || e.pointerType === "touch") return;
        if (e.target.closest("a,button,input,select,textarea,summary")) return;
        start(kaart, e, root, opties);
      });
    });
  };

  function start(kaart, e0, root, opties) {
    var pid = kaart.getAttribute("data-pid");
    var vak = kaart.getBoundingClientRect();
    var dx = e0.clientX - vak.left, dy = e0.clientY - vak.top;
    var ghost = null, kolom = null, bezig = false;

    function beweeg(e) {
      if (!bezig) {
        if (Math.abs(e.clientX - e0.clientX) < DREMPEL &&
            Math.abs(e.clientY - e0.clientY) < DREMPEL) return;
        bezig = true;
        window.__pdrag = true;            // de klik-naar-detail-hook slaat deze beurt over
        ghost = kaart.cloneNode(true);
        ghost.className = kaart.className + " pdrag-ghost";
        ghost.style.width = vak.width + "px";
        document.body.appendChild(ghost);
        kaart.classList.add("pdrag-bron");
      }
      // DE AFFORDANCE ZELF: opschalen, kantelen, en meebewegen. Eén transform, dus de browser
      // hoeft niets te herberekenen buiten de compositielaag.
      ghost.style.transform = "translate3d(" + (e.clientX - dx) + "px," + (e.clientY - dy) +
                              "px,0) scale(1.04) rotate(-2deg)";
      var onder = kolomOnder(e.clientX, e.clientY, root);
      if (onder !== kolom) {
        if (kolom) kolom.classList.remove("over");
        kolom = onder;
        if (kolom) kolom.classList.add("over");
      }
    }

    function stop(e) {
      document.removeEventListener("pointermove", beweeg);
      document.removeEventListener("pointerup", stop);
      document.removeEventListener("pointercancel", stop);
      if (!bezig) return;                 // het was een klik; die mag zijn gang gaan
      if (ghost) ghost.remove();
      kaart.classList.remove("pdrag-bron");
      var naar = kolom && kolom.getAttribute("data-to");
      if (kolom) kolom.classList.remove("over");
      // De vlag pas ná deze beurt terug: anders opent de klik die bij het loslaten hoort
      // alsnog de kaart.
      setTimeout(function () { window.__pdrag = false; }, 60);
      if (naar && naar !== huidigeKolom(kaart)) opties.onDrop(pid, naar);
    }

    document.addEventListener("pointermove", beweeg);
    document.addEventListener("pointerup", stop);
    document.addEventListener("pointercancel", stop);
  }

  // De kolom onder de pointer. Via `elementFromPoint` en niet via de muis-events van de kolom
  // zelf: de ghost hangt onder de cursor, en een element dat de pointer opvangt zou elke
  // dragover-achtige meting vertroebelen (vandaar ook `pointer-events:none` op `.pdrag-ghost`).
  function kolomOnder(x, y, root) {
    var el = document.elementFromPoint(x, y);
    var kol = el && el.closest ? el.closest(".pcol[data-to]") : null;
    return kol && (root === document || root.contains(kol)) ? kol : null;
  }

  function huidigeKolom(kaart) {
    var kol = kaart.closest(".pcol[data-to]");
    return kol ? kol.getAttribute("data-to") : null;
  }

  /* ── De checklist beweegt mee bij de klik (fase 11, laag 2 en 3, prototype sectie 3) ──────
   *
   * HIER EN NIET IN HET FRAGMENT, en dat verschil is precies wat de handmatige doorloop van
   * 20 september blootlegde. Dit stond als `<script>` ín de checklist-HTML, en dat werkt op een
   * volle pagina — maar de projectkaart opent normaal in de MODAL, en die zet zijn inhoud met
   * `innerHTML`. Een script dat zo binnenkomt voert de browser nooit uit. De microinteractie was
   * dus onzichtbaar op precies de plek waar je hem het vaakst zou zien, zonder dat iets faalde.
   *
   * Eén gedelegeerde listener op `document` heeft dat probleem niet: hij bestaat al vóór het
   * fragment er is, en blijft gelden voor elk fragment dat erna komt.
   *
   * WAT DIT NIET IS: een tweede opslagpad. De POST eronder blijft wat hij was en is leidend; dit
   * raakt alleen wat je ZIET, in de seconde tussen je klik en de herlaadbeurt. Zonder JS gebeurt
   * precies wat er altijd gebeurde.
   *
   * De teller telt niet opnieuw maar verschuift met één, vanaf het getal dat de SERVER gaf:
   * overgeslagen items tellen daar niet mee in de noemer, dus zelf tellen zou hier iets anders
   * betekenen dan daar. Een `.b-skip`-vakje doet daarom niets.
   */
  document.addEventListener("click", function (e) {
    var b = e.target.closest ? e.target.closest(".ck-box[data-ck-item]") : null;
    if (!b || b.classList.contains("b-skip")) return;
    var id = b.getAttribute("data-ck-item"), was = b.getAttribute("data-ck-done") === "1";
    b.classList.toggle("on", !was);
    b.textContent = was ? "" : "\u2713";
    b.setAttribute("data-ck-done", was ? "0" : "1");
    var li = b.closest(".ck-item"), t = li && li.querySelector(".ck-txt>span");
    if (t) t.classList.toggle("ck-done", !was);
    var bar = document.querySelector('progress[data-ck-bar="' + id + '"]');
    if (!bar) return;
    var tot = parseInt(bar.getAttribute("data-ck-tot") || "0", 10);
    if (!tot) return;
    var done = Math.round((bar.value * tot) / 100) + (was ? -1 : 1);
    done = Math.max(0, Math.min(tot, done));
    var pct = Math.round((100 * done) / tot);
    bar.value = pct;
    var tel = document.querySelector('[data-ck-tel="' + id + '"]');
    if (tel) tel.textContent = pct + "% (" + done + "/" + tot + ")";
  });

  // Idempotent: `data-nv-wired` per formulier, zodat een fragment dat opnieuw langskomt geen
  // tweede listener krijgt. Een dubbele listener post elke actie twee keer.
  NV.wire = function (root) {
    root = root || document;
    root.querySelectorAll("form[data-qa-frag]").forEach(quickAdd);
    barReset(root);
    inlineEdit(root);
    mdPreview(root);
  };

  if (document.readyState !== "loading") NV.wire(document);
  else document.addEventListener("DOMContentLoaded", function () { NV.wire(document); });
})();
