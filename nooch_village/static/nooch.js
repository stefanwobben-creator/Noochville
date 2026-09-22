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
  // ── De wiki-editor: de tekst zelf is het invoerveld (21 september 2026) ───────────────────
  //
  // Tot vandaag opende "Edit page" een los formulier ONDER de pagina, met een textarea vol ruwe
  // markdown terwijl de opgemaakte tekst gewoon bovenaan bleef staan. Twee kopieën van dezelfde
  // inhoud, en typen op een andere plek dan waar je leest. Dit vervangt dat model.
  //
  // WAT HIER BEWUST NIET GEBEURT: markdown maken. Deze code zet alleen `contenteditable` aan,
  // laat de browser zijn eigen opmaak-tags produceren, en stuurt de HTML op. De omzetting naar
  // markdown doet de SERVER (`_md_naar_bron`), want anders staat er een tweede opmaak-kenner
  // naast `_md` en lopen die twee uiteen zodra er één regel bijkomt.
  function wikiEdit(root) {
    var start = root.querySelector("[data-wiki-start]");
    var body = root.querySelector("#wiki-body");
    var titel = root.querySelector("#wiki-titel");
    var form = root.querySelector("#wiki-form");
    var tb = root.querySelector("#wiki-tb");
    if (!start || !body || !titel || !form || start.dataset.nvWired) return;
    start.dataset.nvWired = "1";

    var origineel = { body: body.innerHTML, titel: titel.textContent };
    var bezig = false;

    function editeerbaar(aan) {
      body.contentEditable = aan ? "true" : "false";
      // `plaintext-only` houdt opmaak UIT de titel; een titel met een vetgedrukt woord erin is
      // geen titel maar een zin. Niet elke browser kent de waarde — dan valt hij terug op
      // gewoon bewerkbaar, en de server neemt toch alleen de tekst.
      titel.contentEditable = aan ? "plaintext-only" : "false";
      if (aan && titel.contentEditable !== "plaintext-only") titel.contentEditable = "true";
      body.classList.toggle("wiki-aan", aan);
      titel.classList.toggle("wiki-aan", aan);
      if (tb) tb.hidden = !aan;
      form.hidden = !aan;
      bezig = aan;
    }

    start.addEventListener("click", function () {
      if (bezig) return;
      origineel = { body: body.innerHTML, titel: titel.textContent };
      editeerbaar(true);
      body.focus();
    });

    var annuleer = form.querySelector("[data-wiki-cancel]");
    if (annuleer) annuleer.addEventListener("click", function () {
      body.innerHTML = origineel.body;
      titel.textContent = origineel.titel;
      editeerbaar(false);
    });

    // De werkbalk. `styleWithCSS=false` is de hele reden dat dit zonder library kan: mét CSS
    // levert de browser `<span style="font-weight:bold">`, en dat is geen tag die de server kent
    // — de vetgedrukte tekst zou dan bij het opslaan gewoon gewone tekst worden.
    if (tb) tb.querySelectorAll("[data-wiki-cmd]").forEach(function (knop) {
      knop.addEventListener("mousedown", function (e) { e.preventDefault(); });  // focus blijft staan
      knop.addEventListener("click", function () {
        try { document.execCommand("styleWithCSS", false, false); } catch (e) { /* oud */ }
        document.execCommand(knop.dataset.wikiCmd, false, knop.dataset.wikiArg || null);
        body.focus();
      });
    });

    // Plakken gaat als PLATTE TEKST. Wie een stuk uit Word of een website plakt, brengt anders
    // een halve stylesheet mee; de server gooit die toch weg, en dan zie je pas na het opslaan
    // dat je opmaak verdwenen is. Zo zie je meteen wat je krijgt.
    body.addEventListener("paste", function (e) {
      if (!bezig) return;
      e.preventDefault();
      var tekst = (e.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, tekst);
    });

    form.addEventListener("submit", function () {
      document.getElementById("wiki-titel-veld").value = titel.textContent.trim();
      document.getElementById("wiki-body-veld").value = body.innerHTML;
    });
  }

  // ── De navigatiebalk als accordeon (21 september 2026) ────────────────────────────────────
  //
  // PR, ME en CI waren paginasprongen: je verliet het scherm waar je mee bezig was om een lijst te
  // zien. Nu klapt die lijst open NAAST de balk en blijft je inhoud rechts staan. WI en AD blijven
  // een sprong — daar kies je niets uit een lijst.
  //
  // ÉÉN PANEEL TEGELIJK, en nogmaals klikken sluit. Twee open panelen naast elkaar is geen
  // navigatie meer maar een tweede scherm; en een knop die alleen opent laat de lezer zoeken naar
  // een kruisje dat er niet hoeft te zijn.
  //
  // ZONDER JS BLIJFT ALLES WERKEN: de knoppen dragen hun `href` (Projects → /projects), dus als
  // deze code niet draait is het gewoon weer een link. Daarom `preventDefault` pas NADAT we weten
  // dat we het paneel echt openen.
  function navPaneel(root) {
    var paneel = root.querySelector("#c2-paneel");
    var binnen = root.querySelector("#c2-paneel-in");
    var knoppen = root.querySelectorAll("[data-nav-paneel]");
    if (!paneel || !binnen || !knoppen.length || paneel.dataset.nvWired) return;
    paneel.dataset.nvWired = "1";
    var open = null;

    function sluit() {
      open = null;
      paneel.hidden = true;
      document.body.classList.remove("navpaneel-open");
      Array.prototype.forEach.call(knoppen, function (k) {
        k.setAttribute("aria-expanded", "false");
      });
    }

    function vul(url) {
      return fetch(url, { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
        .then(function (html) {
          binnen.innerHTML = html;
          NV.wire(binnen);
          var z = binnen.querySelector("[data-nav-zoek]");
          if (z) z.focus();
        })
        // Een leeg paneel leest als "er is niets", en dat is iets anders dan "het laden lukte
        // niet". Dezelfde regel als bij de md-voorbeeldknop: fail-soft, maar niet stil.
        .catch(function () {
          binnen.innerHTML = "<p class='muted c2-pleeg'>Could not load this panel. " +
            "Try again, or use the page itself.</p>";
        });
    }

    Array.prototype.forEach.call(knoppen, function (knop) {
      knop.addEventListener("click", function (e) {
        var sleutel = knop.getAttribute("data-nav-paneel");
        e.preventDefault();
        if (open === sleutel) { sluit(); return; }
        open = sleutel;
        Array.prototype.forEach.call(knoppen, function (k) {
          k.setAttribute("aria-expanded", k === knop ? "true" : "false");
        });
        paneel.hidden = false;
        document.body.classList.add("navpaneel-open");
        binnen.innerHTML = "<p class='muted c2-pleeg'>…</p>";
        // De organisatieboom klapt de tak open waar je NU staat. Een fragment weet niet op welke
        // pagina het landt, dus de client geeft het mee — precies wat de oude zijbalk-injectie
        // server-side deed toen de boom nog met elke pagina meekwam.
        var hier = "";
        if (location.pathname === "/node") {
          hier = new URLSearchParams(location.search).get("id") || "";
        }
        vul("/nav-paneel?p=" + encodeURIComponent(sleutel) +
            (hier ? "&hier=" + encodeURIComponent(hier) : ""));
      });
    });

    // Escape sluit. Een paneel dat over je scherm heen staat en alleen met de muis weg kan, is op
    // een toetsenbord een val.
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && open) sluit();
    });

    // Binnen het paneel: een link met `data-nav-frag` vervangt de INHOUD in plaats van te
    // navigeren (het My/All-filter bij Projects, en straks meer). Alles zonder dat attribuut is
    // een gewone link en hoort het paneel te verlaten.
    binnen.addEventListener("click", function (e) {
      var a = e.target.closest("a[data-nav-frag]");
      if (!a) return;
      e.preventDefault();
      vul(a.getAttribute("href"));
    });

    // Live zoeken in het paneel: dezelfde bron als de dropdown (`/search`), dus geen tweede
    // parser en geen tweede idee van wat vindbaar is.
    var timer = null;
    binnen.addEventListener("input", function (e) {
      var veld = e.target.closest("[data-nav-zoek]");
      if (!veld) return;
      clearTimeout(timer);
      timer = setTimeout(function () {
        vul("/nav-paneel?p=zoek&q=" + encodeURIComponent(veld.value));
      }, 220);
    });
  }

  // ── De live-knop: draait er een werkoverleg? (21 september 2026) ──────────────────────────
  //
  // POLLING EN GEEN WEBSOCKET, met de meting erbij: de vraag kost 0,31 ms op de server zolang je
  // alleen de store bouwt die hem kan beantwoorden (alle stores bouwen kost 70 ms — zie de route).
  // Vijf mensen die elke 20 seconden vragen is ~0,08 ms serverwerk per seconde. Een websocket-laag
  // is dan infrastructuur voor een probleem dat er niet is.
  //
  // DRIE DINGEN DIE EEN POLLER BESCHAAFD HOUDEN:
  //  * niets vragen als het tabblad verborgen is — een weggeklikt venster hoeft niets te weten;
  //  * bij een fout het interval VERDUBBELEN in plaats van doorrammen (een server die het even
  //    niet trekt, trekt het al helemaal niet met vijf clients die blijven kloppen);
  //  * de server stuurt HTML terug, geen JSON: zo bepaalt één plek hoe een live-knop eruitziet.
  function overlegPoll(root) {
    var houder = root.querySelector(".c2-subnav");
    if (!houder || houder.dataset.nvPoll) return;
    var eerste = houder.querySelector("a.c2-overleg");
    if (!eerste) return;                                  // geen cirkel, geen knoppen, niets te doen
    var m = /circle=([^&]+)/.exec(eerste.getAttribute("href") || "");
    if (!m) return;
    houder.dataset.nvPoll = "1";

    var BASIS = 20000, wacht = BASIS, timer = null;

    function plan(ms) { clearTimeout(timer); timer = setTimeout(vraag, ms); }

    function vraag() {
      if (document.hidden) { plan(BASIS); return; }
      fetch("/overleg-status?circle=" + encodeURIComponent(m[1]), { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.text() : Promise.reject(r.status); })
        .then(function (html) {
          wacht = BASIS;
          // Alleen vervangen als er écht iets anders staat: anders verliest een knop die je net
          // aanwijst zijn hover, en een schermlezer leest hem elke 20 seconden opnieuw voor.
          var nu = Array.prototype.map.call(houder.querySelectorAll("a.c2-overleg"),
                                            function (a) { return a.outerHTML; }).join("");
          if (nu === html) return;
          Array.prototype.forEach.call(houder.querySelectorAll("a.c2-overleg"), function (a, i) {
            if (i === 0) a.insertAdjacentHTML("beforebegin", html);
            a.remove();
          });
        })
        .catch(function () { wacht = Math.min(wacht * 2, 5 * 60 * 1000); })
        .then(function () { plan(wacht); });
    }

    // Terug op het tabblad = meteen kijken. Wie terugkomt na een half uur wil niet nog twintig
    // seconden naar een knop staren die niet klopt.
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) plan(200);
    });
    plan(BASIS);
  }

  // ── Stickers zoeken in het eigen Giphy-kanaal ─────────────────────────────────────────────
  // ALLEEN DE ONDERSTE HELFT VAN DE KIEZER. De vaste rij is HTML die er al staat, met een
  // formulier per sticker: die werkt zonder JavaScript en blijft werken als Giphy eruit ligt.
  // Dit stuk vult alleen het vak eronder.
  //
  // ER REIST GEEN URL MEE, alleen het Giphy-id. Wat de server ophaalt hoort de server te
  // bepalen — zie `giphy.haal` en `giphy.download` voor de andere kant van die regel.
  function giphyZoek(pop) {
    if (pop.dataset.nvGiphy) return;
    pop.dataset.nvGiphy = "1";
    var veld = pop.querySelector("[data-giphy-q]");
    var uit = pop.querySelector("[data-giphy-uit]");
    if (!veld || !uit) return;
    var kanaal = pop.getAttribute("data-kanaal") || "";
    var csrf = pop.getAttribute("data-csrf") || "";
    var timer = null;

    function leeg(bericht) {
      uit.textContent = "";
      if (bericht) {
        var p = document.createElement("p");
        p.className = "muted";
        p.textContent = bericht;
        uit.appendChild(p);
      }
    }

    function toon(hits) {
      leeg(hits.length ? "" : "Nothing in the Nooch channel for that.");
      hits.forEach(function (h) {
        // Eén formulier per treffer, precies zoals de vaste rij erboven: dezelfde actie-vorm,
        // dezelfde knop. Zo is er geen tweede manier om een sticker te plaatsen.
        var f = document.createElement("form");
        f.method = "post";
        f.action = "/action";
        f.className = "emo-f";
        f.innerHTML = "<input type='hidden' name='csrf'><input type='hidden' name='kanaal'>"
          + "<input type='hidden' name='next'>"
          + "<input type='hidden' name='gif'><button class='emo' type='submit' "
          + "name='action' value='giphy_post'><img loading='lazy'></button>";
        f.querySelector("[name=csrf]").value = csrf;
        f.querySelector("[name=kanaal]").value = kanaal;
        f.querySelector("[name=next]").value = location.pathname + location.search;
        f.querySelector("[name=gif]").value = h.id;
        var img = f.querySelector("img");
        img.src = h.url;
        img.alt = h.naam || "sticker";
        f.querySelector("button").title = h.naam || "sticker";
        uit.appendChild(f);
      });
    }

    veld.addEventListener("input", function () {
      clearTimeout(timer);
      var q = veld.value.trim();
      if (!q) { leeg(""); return; }
      timer = setTimeout(function () {
        fetch("/giphy-zoek?q=" + encodeURIComponent(q), { credentials: "same-origin" })
          .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
          .then(function (d) { return d.hits || []; },
                // FAIL-SOFT, ZICHTBAAR MAAR RUSTIG. Giphy eruit betekent niet dat de kiezer
                // stuk is: de rij erboven doet het nog. Dus één regel tekst, geen foutmelding.
                function () { return null; })
          .then(function (hits) { if (hits === null) leeg("Sticker search is unavailable."); else toon(hits); });
      }, 250);
    });
  }

  function stickers(root) {
    root.querySelectorAll("[data-giphy]").forEach(giphyZoek);
  }

  // ── @-vermelding: typhulp bij het typen ───────────────────────────────────────────────────
  // Zet `data-mention` op een <textarea> of <input> en hij krijgt een @-lijst. Verder niets:
  // de keuze wordt PLATTE TEKST ("@Stefan Wobben "). Geen notificatie, geen link, geen
  // koppeling — dat is een apart besluit, en wel een met een eigen autorisatievraag.
  //
  // DRIE DINGEN DIE DE INLINE-VERSIE OP DE PROJECTFEED NIET HEEFT, en de reden dat dit er staat:
  //  * de lijst komt van de SERVER (`/mention-search`) in plaats van uit een volledige
  //    namenlijst die met elke pagina meereist — die groeit mee met de organisatie en staat
  //    in elk scherm waar je hem ooit nodig zou kunnen hebben;
  //  * pijltjes + Enter, niet alleen muis. Wie typt heeft zijn handen al op het toetsenbord;
  //  * de lijst hangt op de BODY met paginacoördinaten, dus het veld hoeft zelf geen
  //    positie-context te hebben (de inline-versie zet daarvoor `parentNode.style.position`,
  //    en dat is een stijl-wijziging aan iemand anders' element).
  function mentionVeld(veld) {
    if (veld.dataset.nvMention) return;                       // dubbel bedraden = dubbele lijst
    veld.dataset.nvMention = "1";

    var pop = null, hits = [], idx = -1, timer = null, teller = 0;

    // Het @-woord waar de cursor NU in staat. Voorwaarde: de @ staat aan het begin of na
    // witruimte — anders zou een e-mailadres ("a@b") de lijst openen.
    function token() {
      var tot = veld.value.slice(0, veld.selectionStart);
      var m = /(^|\s)@([^\s@]{0,40})$/.exec(tot);
      return m ? { term: m[2], start: tot.length - m[2].length - 1 } : null;
    }

    function sluit() {
      if (pop) { pop.remove(); pop = null; }
      hits = []; idx = -1;
      veld.removeAttribute("aria-activedescendant");
      veld.setAttribute("aria-expanded", "false");
    }

    function plaats() {
      if (!pop) return;
      var r = veld.getBoundingClientRect();
      pop.style.left = (r.left + window.pageXOffset) + "px";
      pop.style.top = (r.bottom + window.pageYOffset + 4) + "px";
    }

    function merk() {
      Array.prototype.forEach.call(pop.children, function (el, i) {
        el.setAttribute("aria-selected", i === idx ? "true" : "false");
      });
      if (idx >= 0) {
        veld.setAttribute("aria-activedescendant", pop.children[idx].id);
        pop.children[idx].scrollIntoView({ block: "nearest" });
      }
    }

    function kies(i) {
      // HET @-WOORD WORDT HIER OPNIEUW OPGEZOCHT en niet onthouden vanaf het moment dat de
      // lijst werd opgehaald. Dat was de bug: `toon()` begint met opruimen, en dat wiste de
      // onthouden positie — pijltjes werkten, Enter deed niets. Een positie in een tekst die
      // ondertussen kan veranderen is afgeleide informatie; die hoor je af te leiden.
      var t = token();
      if (i < 0 || i >= hits.length || !t) return;
      var caret = veld.selectionStart;
      var voor = veld.value.slice(0, t.start) + "@" + hits[i].label + " ";
      veld.value = voor + veld.value.slice(caret);
      veld.focus();
      veld.selectionStart = veld.selectionEnd = voor.length;
      sluit();
      // Andere bedrading (tellers, "er staat iets getypt"-knoppen) hoort dit te merken: wij
      // veranderden de waarde met de hand, en dan komt er geen `input`-event vanzelf.
      veld.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function toon(lijst) {
      sluit();
      if (!lijst.length) return;
      hits = lijst;
      pop = document.createElement("div");
      pop.className = "mention-pop";
      pop.setAttribute("role", "listbox");
      lijst.forEach(function (h, i) {
        var b = document.createElement("button");
        b.type = "button";                       // anders is het in een formulier een submit
        b.className = "mention-it";
        b.id = "nv-ment-" + (++teller);
        b.setAttribute("role", "option");
        b.setAttribute("aria-selected", "false");
        var k = document.createElement("span");
        k.className = "gs-kind gs-" + (h.kind || "role");
        k.textContent = h.kind || "role";
        b.appendChild(k);
        b.appendChild(document.createTextNode("@" + h.label));
        // mousedown i.p.v. click: klikken haalt eerst de focus uit het veld, en dan is de
        // cursorpositie weg waar we net in wilden invoegen.
        b.addEventListener("mousedown", function (ev) { ev.preventDefault(); kies(i); });
        pop.appendChild(b);
      });
      document.body.appendChild(pop);
      idx = 0; merk(); plaats();
      veld.setAttribute("aria-expanded", "true");
    }

    function vraag() {
      var t = token();
      if (!t) { sluit(); return; }
      fetch("/mention-search?q=" + encodeURIComponent(t.term), { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (d) {
          // Tussen vraag en antwoord kan de cursor verder zijn; dan is dit antwoord verouderd.
          var nu = token();
          return (nu && nu.term === t.term) ? (d.hits || []) : null;
        }, function () { sluit(); return null; })  // stil: typhulp die faalt hoort niet te schreeuwen
        // BEWUST BUITEN DIE CATCH. Een netwerkfout mag stil zijn, een fout in het TEKENEN niet:
        // met één catch om het hele blok verdween een echte bug in de stilte (zie `kies`).
        .then(function (lijst) { if (lijst) toon(lijst); });
    }

    veld.setAttribute("aria-expanded", "false");
    veld.addEventListener("input", function () {
      clearTimeout(timer);
      if (!token()) { sluit(); return; }
      timer = setTimeout(vraag, 120);              // niet per aanslag naar de server
    });

    veld.addEventListener("keydown", function (ev) {
      if (!pop) return;
      if (ev.key === "ArrowDown") { ev.preventDefault(); idx = (idx + 1) % hits.length; merk(); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); idx = (idx - 1 + hits.length) % hits.length; merk(); }
      else if (ev.key === "Enter" || ev.key === "Tab") { ev.preventDefault(); kies(idx); }
      else if (ev.key === "Escape") { ev.preventDefault(); sluit(); }
    });

    veld.addEventListener("blur", function () { setTimeout(sluit, 150); });
    window.addEventListener("resize", plaats);
  }

  function mentions(root) {
    root.querySelectorAll("[data-mention]").forEach(mentionVeld);
  }

  NV.wire = function (root) {
    root = root || document;
    root.querySelectorAll("form[data-qa-frag]").forEach(quickAdd);
    barReset(root);
    inlineEdit(root);
    mdPreview(root);
    wikiEdit(root);
    navPaneel(root);
    overlegPoll(root);
    stickers(root);
    mentions(root);
  };

  if (document.readyState !== "loading") NV.wire(document);
  else document.addEventListener("DOMContentLoaded", function () { NV.wire(document); });
})();
