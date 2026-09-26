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

  /* `NV.sleep` IS HET GEDEELDE STUK, `NV.bord` de eerste aanroeper (brok 3, 22 september 2026).
   * Hiervoor stonden de selectors van het bord (`.pcard`, `.pcol`) ín deze functie gebakken. De
   * wiki-blokken willen exact hetzelfde gedrag met andere selectors, en een tweede implementatie
   * zou betekenen dat de ene na een wijziging anders sleept dan de andere.
   *
   *   opties.kaart   selector van het sleepbare ding, met zijn id-attribuut
   *   opties.id      attribuut waar de identiteit in staat (`data-pid`, `data-blok-id`, …)
   *   opties.doel    selector van het vak waarin je hem kunt laten vallen
   *   opties.naar    attribuut op dat vak met de bestemming
   *   opties.greep  optioneel: alleen een pointerdown hierbinnen start het slepen
   *   opties.onDrop(id, naar, e)  `e` is de pointerup — voor wie de positie nodig heeft
   */
  NV.sleep = function (root, opties) {
    root = root || document;
    opties = opties || {};
    if (!opties.onDrop || !opties.kaart || !opties.doel) return;
    root.querySelectorAll(opties.kaart).forEach(function (kaart) {
      if (kaart.getAttribute("data-nv-sleep")) return;
      kaart.setAttribute("data-nv-sleep", "1");
      // De native vlag uit: anders vecht de browser-drag met deze.
      kaart.setAttribute("draggable", "false");
      kaart.addEventListener("pointerdown", function (e) {
        if (e.button !== 0 || e.pointerType === "touch") return;
        // MET `opties.greep` BEGINT HET SLEPEN ALLEEN DAAR. Op het bord pak je de kaart zelf;
        // in een bewerkbaar veld zou dat vechten met het selecteren van woorden, dus daar is
        // er één plek om beet te pakken.
        if (opties.greep) {
          if (!e.target.closest(opties.greep)) return;
        } else if (e.target.closest("a,button,input,select,textarea,summary")) {
          return;
        }
        start(kaart, e, root, opties);
      });
    });
  };

  NV.bord = function (root, opties) {
    opties = opties || {};
    if (!opties.onDrop) return;
    NV.sleep(root, {
      kaart: ".pcard[data-pid]", id: "data-pid",
      doel: ".pcol[data-to]", naar: "data-to",
      onDrop: opties.onDrop
    });
  };

  function start(kaart, e0, root, opties) {
    var pid = kaart.getAttribute(opties.id);
    var vak = kaart.getBoundingClientRect();
    var dx = e0.clientX - vak.left, dy = e0.clientY - vak.top;
    var ghost = null, kolom = null, bezig = false, laatsteKant = "";

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
      var onder = vakOnder(e.clientX, e.clientY, root, opties.doel);
      // MET `opties.helft` TELT OOK DE KANT. Een kaart valt in een KOLOM en daar is geen boven of
      // onder; een blok valt VÓÓR of NÁ een ander blok, en `onDrop` beslist dat op de muispositie.
      // Zonder dit zag je tijdens het slepen wel je doel maar niet aan welke kant je landt — en
      // dat is precies de helft van de vraag.
      var kant = "";
      if (opties.helft && onder) {
        var vk = onder.getBoundingClientRect();
        kant = e.clientY < vk.top + vk.height / 2 ? "over-boven" : "over-onder";
      }
      if (onder !== kolom || kant !== laatsteKant) {
        if (kolom) kolom.classList.remove("over", "over-boven", "over-onder");
        kolom = onder;
        laatsteKant = kant;
        if (kolom) kolom.classList.add(kant || "over");
      }
    }

    function stop(e) {
      document.removeEventListener("pointermove", beweeg);
      document.removeEventListener("pointerup", stop);
      document.removeEventListener("pointercancel", stop);
      if (!bezig) return;                 // het was een klik; die mag zijn gang gaan
      if (ghost) ghost.remove();
      kaart.classList.remove("pdrag-bron");
      var naar = kolom && kolom.getAttribute(opties.naar);
      if (kolom) kolom.classList.remove("over", "over-boven", "over-onder");
      // De vlag pas ná deze beurt terug: anders opent de klik die bij het loslaten hoort
      // alsnog de kaart.
      setTimeout(function () { window.__pdrag = false; }, 60);
      // De POSITIE gaat mee: een kaart valt in een kolom, maar een blok valt vóór of ná een
      // ander blok. Het bord negeert dit derde argument.
      if (naar && naar !== huidigVak(kaart, opties)) opties.onDrop(pid, naar, e);
    }

    document.addEventListener("pointermove", beweeg);
    document.addEventListener("pointerup", stop);
    document.addEventListener("pointercancel", stop);
  }

  // De kolom onder de pointer. Via `elementFromPoint` en niet via de muis-events van de kolom
  // zelf: de ghost hangt onder de cursor, en een element dat de pointer opvangt zou elke
  // dragover-achtige meting vertroebelen (vandaar ook `pointer-events:none` op `.pdrag-ghost`).
  function vakOnder(x, y, root, sel) {
    var el = document.elementFromPoint(x, y);
    var kol = el && el.closest ? el.closest(sel) : null;
    return kol && (root === document || root.contains(kol)) ? kol : null;
  }

  function huidigVak(kaart, opties) {
    var kol = kaart.closest(opties.doel);
    return kol ? kol.getAttribute(opties.naar) : null;
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
  /* ── De normaliseerpas: het blokmodel heel houden (brok 3, 22 september 2026) ─────────────
   *
   * WAT ER STUK GAAT ZONDER DEZE PAS, gemeten in de echte editor en niet bedacht:
   *
   *     formatBlock         VERVANGT het `.wb`-omhulsel → er staat een kale <h4> op het hoogste
   *                         niveau, zonder klasse en zonder `data-blok`
   *     insertUnorderedList NEST een <ul> ín het omhulsel → `data-blok="p"` blijft staan terwijl
   *                         er een lijst in zit
   *
   * Sinds brok 1 is dat omhulsel het ding waar de greep aan hangt en waarop `closest('.wb')`
   * werkt. Eén druk op de H-knop van de bestaande werkbalk maakte dat al kapot — deze pas is
   * dus een reparatie, geen voorwerk.
   *
   * HIJ IS BEWUST DOM. Hij kent geen markdown en geen syntaxis: hij kijkt naar de TAG van de
   * inhoud en zet het bijbehorende `data-blok`. Die tabel komt van de server mee als
   * `data-blok-soorten`; er is hier geen tweede lijst. Dat is geen voorzichtigheid maar
   * noodzaak: er is in deze stack geen JS-testrunner, dus hoe minder dit weet, hoe minder er
   * stil kan afwijken. Wat niet in de tabel staat is een alinea.
   */
  NV.blokNormaliseer = function (body) {
    if (!body) return;
    var soorten = {};
    try { soorten = JSON.parse(body.getAttribute("data-blok-soorten") || "{}"); } catch (e) { return; }
    // Zonder tabel geen oordeel: dan is elk blok even geldig en doen we niets.
    if (!Object.keys(soorten).length) return;

    function soortVan(el) {
      return (el && soorten[el.tagName.toLowerCase()]) || "p";
    }
    // De inhoud van een blok is het eerste element dat GEEN chrome is (de greep uit stap 2).
    function inhoudVan(blok) {
      var k = blok.firstElementChild;
      while (k && k.hasAttribute("data-chrome")) k = k.nextElementSibling;
      return k;
    }

    Array.prototype.slice.call(body.childNodes).forEach(function (node) {
      if (node.nodeType === 3) {
        // Kale tekst op het hoogste niveau: witruimte weg, echte tekst in een blok.
        if (!node.textContent.trim()) { node.remove(); return; }
        var omhulsel = document.createElement("div");
        body.insertBefore(omhulsel, node);
        omhulsel.appendChild(node);
        omhulsel.className = "wb";
        omhulsel.setAttribute("data-blok", "p");
        return;
      }
      if (node.nodeType !== 1) return;
      // EEN OPEN BEWERKVLAK BLIJFT WAT HET IS. Zonder dit ziet de pas alleen een <textarea>,
      // vindt die niet in de soorten-tabel, en maakt er een alinea van — precies het blok dat je
      // aan het bewerken bent verliest dan zijn identiteit.
      if (node.querySelector && node.querySelector("[data-blok-bron]")) return;
      // EN OP HET BLOK ZELF. Het afgeleide blok (feiten, backlinks) draagt zijn bron in een
      // attribuut op het OMHULSEL en niet in een veld erbínnen, dus de regel hierboven — die
      // alleen naar afstammelingen kijkt — liep er langs. Zonder deze regel zet de pas
      // `data-blok` terug op `p`, want de tag is een `div`: het blok is dan zijn soort kwijt en
      // de greep, het menu en de vormgeving zien een gewone alinea. Gemeten in Chrome op
      // 24 september 2026 — de servertoetsen zagen dit niet, want zij draaien geen pas.
      if (node.hasAttribute && node.hasAttribute("data-blok-bron")) return;
      // EEN TAAK-BLOK IS EEN LIJST MET VINKJES. De pas kent alleen tag→soort, en de tag is hier
      // `ul`; zonder deze regel zet hij `data-blok` terug op `ul` en is het blok zijn identiteit
      // kwijt. De soort wordt door de wiki-laag gezet (zie `views/wiki._body_html`), niet door
      // de soorten-tabel, dus de pas moet hem met rust laten.
      if (node.dataset && node.dataset.blok === "taak" &&
          node.querySelector && node.querySelector("input[type=checkbox]")) return;
      if (node.classList.contains("wb")) {
        // EIGEN TAG EERST, en dat is geen detail: Firefox HERNOEMT het omhulsel op zijn plek
        // (`DIV.wb[data-blok=p]` wordt `BLOCKQUOTE.wb[data-blok=p]`) waar Chrome het VERVANGT
        // door een kale tag die hieronder opnieuw wordt ingepakt. Keek de pas alleen naar de
        // inhoud, dan vond hij in de hernoemde versie alleen de greep en bleef er `p` staan —
        // gemeten in Firefox 154 op 23 september 2026. De server maakt van beide vormen
        // hetzelfde markdown, dus dit raakt niet wat je opslaat; het raakt wel wat de greep
        // en het scherm van het blok denken.
        node.setAttribute("data-blok", soorten[node.tagName.toLowerCase()]
                                       || soortVan(inhoudVan(node)));
        return;
      }
      // Een kale tag (wat `formatBlock` achterlaat): er een omhulsel omheen.
      var soort = soortVan(node);
      var wrap = document.createElement("div");
      body.insertBefore(wrap, node);
      wrap.appendChild(node);
      wrap.className = "wb";
      wrap.setAttribute("data-blok", soort);
    });

    /* \u00c9\u00c9N BOLLETJE IS \u00c9\u00c9N BLOK, ook na typen (26 september 2026).
     *
     * De server levert elk lijstitem als eigen `.wb`, maar de BROWSER doet dat niet: druk je Enter
     * in een bolletje, dan zet hij er een tweede `<li>` bij in dezelfde `<ul>`. Zonder deze pas
     * groeit een lijst dus vanzelf weer terug naar \u00e9\u00e9n blok met \u00e9\u00e9n greep \u2014 precies het euvel dat
     * hierboven is weggehaald.
     *
     * DE EERSTE `<li>` BLIJFT IN ZIJN EIGEN BLOK ZITTEN en de rest krijgt een kopie van het
     * omhulsel. Zo blijft de greep die er al hing bij het item waar hij bij hoorde.
     */
    body.querySelectorAll(":scope > .wb").forEach(function (blok) {
      // VIA HET ITEM EN NIET VIA DE LIJST-TAG. Dit bestand noemt geen bloktypes bij naam —
      // `test_javascript_draagt_geen_eigen_soorten_lijst` verbiedt dat, en terecht: een tweede
      // lijst van soorten loopt uiteen zodra er één bijkomt. Een `<li>` is geen bloksoort maar
      // het onderdeel waar dit over gaat, en zijn ouder is per definitie de lijst.
      var eerste = blok.querySelector("li");
      if (!eerste) return;
      var lijst = eerste.parentNode;
      if (!lijst || lijst.parentNode !== blok) return;   // genest lijstje: met rust laten
      var items = lijst.children;
      if (items.length < 2) return;
      var volgende = blok.nextSibling;
      // DE NUMMERING LOOPT DOOR terwijl je typt. Zonder dit begint elke losse `<ol>` weer bij 1
      // en staat er "1. 1. 1." op het scherm tot je opslaat; de server rekent hem daarna opnieuw
      // uit, maar wat je ziet moet ook kloppen.
      var begin = parseInt(lijst.getAttribute("start") || "1", 10) || 1;
      Array.prototype.slice.call(items, 1).forEach(function (li, i) {
        var wrap = blok.cloneNode(false);            // zelfde klassen en soort, geen inhoud
        wrap.removeAttribute("data-blok-id");        // `grepen()` nummert zo meteen opnieuw
        var nieuweLijst = lijst.cloneNode(false);    // zelfde tag en klasse, zonder items
        // `start` ONVOORWAARDELIJK, want dit bestand weet niet welke lijstsoort dit is en hoort
        // dat ook niet te weten. Een bolletjeslijst negeert het attribuut — de browser doet er
        // niets mee en de weg terug leest het alleen bij een genummerde lijst.
        nieuweLijst.setAttribute("start", begin + i + 1);
        nieuweLijst.appendChild(li);
        wrap.appendChild(nieuweLijst);
        body.insertBefore(wrap, volgende);
      });
    });

    // EEN BLOK IN EEN BLOK IS GEEN BLOK MEER: `closest('.wb')` zou dan het verkeerde ding pakken.
    // Dit gebeurt als de browser bij het slepen of plakken een bestaand blok in een ander schuift.
    body.querySelectorAll(".wb .wb").forEach(function (diep) {
      diep.classList.remove("wb");
      diep.removeAttribute("data-blok");
    });
  };

  /* ── De greep: één plek om een blok beet te pakken (brok 3, stap 2) ──────────────────────
   *
   * CHROME IN EEN BEWERKBAAR VELD, en dat is precies het lastige. Alles binnen `#wiki-body` gaat
   * bij het opslaan mee als `innerHTML`, en de server maakt van een tag die hij niet kent zijn
   * eigen TEKST. Gemeten vóór dit bestond: een knop in een blok gaf na opslaan letterlijk
   * `⠿Een alinea.` in de bron. Twee verdedigingen dus, en allebei nodig:
   *
   *   1. de editor haalt elk `[data-chrome]` eruit vóór het versturen (zie de submit-handler);
   *   2. de server negeert `data-chrome` in plaats van het tot tekst te maken (`_BronParser`).
   *
   * `contenteditable="false"` houdt de cursor eruit. Zonder dat typt iemand vroeg of laat ín
   * zijn eigen greep, en dan staat er een ⠿ midden in een zin.
   *
   * HET MENU IS DE WEG ZONDER SLEPEN. Op touch sleept dit dorp niet (zelfde regel als het bord:
   * een sleepgebaar dat scrollen blokkeert maakt een scherm op een telefoon onbruikbaar) en met
   * een toetsenbord al helemaal niet. Omhoog, omlaag en verwijderen staan daarom in een menu
   * onder dezelfde greep — één affordance, niet drie knopjes naast elkaar.
   */
  var GREEP_ACTIES = [
    // WIJZIG TYPE STAAT BOVENAAN, want het is de enige die de INHOUD raakt; de drie eronder
    // verplaatsen of verwijderen alleen. Hij ontbrak: een blok dat er al stond kon je verplaatsen
    // en weggooien, maar niet omzetten — je moest de tekst knippen, het blok verwijderen, een
    // nieuw blok maken en plakken.
    ["type", "⇄ wijzig type"],
    ["omhoog", "↑ omhoog"],
    ["omlaag", "↓ omlaag"],
    ["verwijder", "✕ verwijderen"]
  ];

  function greepVoor(blok) {
    var g = document.createElement("span");
    g.className = "wb-greep";
    g.setAttribute("data-chrome", "");
    g.contentEditable = "false";
    /* DE PLUS: de ontdekbare helft (25 september 2026). Het `/`-menu werkte al, maar alleen als
     * je wist dat het bestond — er was geen knop, geen hint en geen plek waar het zich
     * aankondigde. Hij hangt in dezelfde goot als de greep en verschijnt op dezelfde hover.
     *
     * HIJ DOET LETTERLIJK WAT TYPEN DOET. Hierboven in `blokMenuKies` staat een gemeten
     * waarschuwing: een leeg blok met een samengevallen selectie heeft geen inhoud om
     * `formatBlock` op te werken, dus dan verandert het bloktype niet. Een plus die een écht leeg
     * blok invoegt loopt recht in dat gat. Daarom: een blok met een `/` erin, en dan het
     * bestaande menu laten opengaan. Eén pad, dat al bewezen is. */
    var plus = document.createElement("button");
    plus.type = "button";
    plus.className = "wb-plus";
    plus.setAttribute("aria-label", "Add a block below");
    plus.setAttribute("title", "Add a block below");
    plus.textContent = "+";
    plus.addEventListener("click", function (e) {
      e.preventDefault();
      nieuwBlokOnder(blok);
    });
    g.appendChild(plus);

    var knop = document.createElement("button");
    knop.type = "button";
    knop.className = "wb-greep-knop";
    // WAAROM HIER EEN TOOLTIP STAAT. Klikken opent een menu, dus het icoontje leest als een
    // menuknop — en zo belandde "geen drag-and-drop" in een ontwerpdocument terwijl slepen al
    // werkte. De `cursor:grab` is er wel, maar die zie je pas als je er al bent.
    // Engels, zoals de rest van de UI sinds i18n-fase 1.
    knop.setAttribute("aria-label", "Drag to move this block, or click for options");
    knop.setAttribute("title", "Drag to move \u00b7 click for options");
    knop.textContent = "⠿";
    g.appendChild(knop);
    var menu = document.createElement("span");
    menu.className = "wb-menu";
    menu.hidden = true;
    var acties = GREEP_ACTIES.slice();
    // EEN TABEL EN EEN CODEBLOK BEWERK JE ALS TEKST. `contenteditable` en `execCommand` kunnen
    // die twee niet fatsoenlijk aan: een Enter in een cel maakt iets anders dan een nieuwe rij,
    // en een blokcommando op een <pre> haalt de regelovergangen eruit. Daarom een eigen ingang,
    // en alleen bij die twee soorten — bij een alinea zou hij verwarrend zijn.
    if (blok.dataset.blok === "tabel" || blok.dataset.blok === "code") {
      acties.unshift(["bron", "✎ bewerk als tekst"]);
    }
    acties.forEach(function (paar) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = "wb-menu-item";
      b.setAttribute("data-wb-actie", paar[0]);
      b.textContent = paar[1];
      menu.appendChild(b);
    });
    g.appendChild(menu);
    knop.addEventListener("click", function (e) {
      e.preventDefault();
      // Eén menu tegelijk: twee open menu's laten je raden bij welk blok je bezig bent.
      blok.closest("[data-blok-soorten]").querySelectorAll(".wb-menu").forEach(function (m) {
        if (m !== menu) m.hidden = true;
      });
      menu.hidden = !menu.hidden;
    });
    menu.addEventListener("click", function (e) {
      var b = e.target.closest("[data-wb-actie]");
      if (!b) return;
      e.preventDefault();
      menu.hidden = true;
      blokActie(blok, b.getAttribute("data-wb-actie"));
    });
    return g;
  }

  /* Een nieuw blok onder dit blok, met het menu er meteen bij open.
   *
   * DE `input`-GEBEURTENIS IS GEEN TRUC MAAR DE HELE BEDOELING. Het menu hangt aan één plek
   * (`blokMenu`, die luistert op `input` en opengaat bij een blok dat precies "/" bevat). Zou de
   * plus zijn eigen menu openen, dan waren er twee plekken die beslissen wanneer dat menu
   * verschijnt — en die lopen na één wijziging uiteen. Hier zetten we de caret in het nieuwe blok
   * en laten we dat ene mechanisme zijn werk doen. */
  function nieuwBlokOnder(blok) {
    var body = blok.parentNode;
    var nieuw = document.createElement("div");
    nieuw.className = "wb";
    nieuw.setAttribute("data-blok", "p");
    nieuw.textContent = "/";
    body.insertBefore(nieuw, blok.nextSibling);
    grepen(body, true);
    // De caret ACHTER de streep, zodat het blok "/" bevat en het menu hem herkent.
    var tekst = streepNode(nieuw);
    if (tekst) {
      var r = document.createRange();
      r.setStart(tekst, tekst.length);
      r.collapse(true);
      var sel = getSelection();
      sel.removeAllRanges();
      sel.addRange(r);
    }
    body.focus();
    body.dispatchEvent(new Event("input", { bubbles: true }));
  }

  /* De selectie in een `<code>` zetten. Er is geen `execCommand` voor inline code, dus dit is de
   * enige knop in de werkbalk die zelf iets maakt.
   *
   * `insertHTML` EN NIET `surroundContents`: die laatste gooit een fout zodra de selectie een
   * elementgrens kruist (half vet, half gewoon), en dat is precies het soort selectie dat iemand
   * per ongeluk maakt. `insertHTML` laat de browser het opruimen.
   *
   * DE TEKST WORDT GE-ESCAPED. Wat je selecteert is TEKST; zou er `<b>` in staan en we plakken
   * hem rauw terug, dan maakt de browser er opmaak van die de schrijver nooit typte.
   *
   * NIET BINNEN EEN CODEBLOK. Daar is elk teken al letterlijk, en een `<code>` ín een
   * `<pre><code>` is precies de vorm die de weg terug bewust negeert — dan zou de inhoud
   * verdwijnen. Zelfde grens als in `_md`, een laag hoger.
   *
   * DE CONTROLE STAAT OP `<code>` EN NIET OP `<pre>`, en dat is geen slordigheid. `nooch.js` mag
   * geen bloktags bij naam noemen (`test_javascript_draagt_geen_eigen_soorten_lijst`: de tabel
   * tag→soort hoort alleen uit `data-blok-soorten` te komen), en `pre` staat in die tabel. Het is
   * bovendien overbodig: `_md` rendert een codeblok altijd als `<pre><code>`, dus elke selectie
   * erbinnen zit óók in een `<code>`. En dat is precies de schade die we willen voorkomen — een
   * `<code>` in een `<code>`.
   */
  function inlineCode() {
    var sel = getSelection();
    if (!sel || !sel.rangeCount) return;
    var r = sel.getRangeAt(0);
    var start = r.startContainer;
    var el = start.nodeType === 1 ? start : start.parentNode;
    if (el && el.closest && (el.closest("code") || el.closest("[data-blok-bron]"))) return;
    var tekst = r.toString();
    if (!tekst) return;                       // niets geselecteerd: geen lege code-chip maken
    var veilig = tekst.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    document.execCommand("insertHTML", false, "<code>" + veilig + "</code>");
    ontharde(el.closest(".wb") || el);
  }

  /* DE HARDE SPATIE DIE CHROME ERBIJ ZET. Gemeten: selecteer "gewone" in "Een gewone alinea" en
   * `insertHTML` levert `Een&nbsp;<code>gewone</code>&nbsp;alinea` — de browser vervangt de
   * spaties naast de invoeging door U+00A0. De rondgang overleeft dat (gecontroleerd), maar in de
   * opgeslagen markdown staat dan een ONZICHTBAAR ander teken dan de schrijver typte, en dat is
   * precies het soort stille vervuiling dat hier al twee keer is opgeruimd (de `\r`-pagina's, de
   * spatie die bij elke bewerkronde aangroeide in het taak-blok).
   *
   * ALLEEN DE RANDTEKENS. Een harde spatie midden in een zin kan iemand bewust hebben geplakt;
   * die blijft staan. Wat hier weggaat is het eerste of laatste teken van een tekstknooppunt dat
   * aan de invoeging grenst — precies waar de browser ze neerzet. */
  function ontharde(blok) {
    if (!blok) return;
    var w = document.createTreeWalker(blok, NodeFilter.SHOW_TEXT, null);
    var n;
    while ((n = w.nextNode())) {
      if (n.parentNode && n.parentNode.closest("[data-chrome]")) continue;
      n.textContent = n.textContent.replace(/^\u00a0/, " ").replace(/\u00a0$/, " ");
    }
  }

  function blokActie(blok, actie) {
    var body = blok.parentNode;
    if (actie === "omhoog" && blok.previousElementSibling) {
      body.insertBefore(blok, blok.previousElementSibling);
    } else if (actie === "omlaag" && blok.nextElementSibling) {
      body.insertBefore(blok.nextElementSibling, blok);
    } else if (actie === "verwijder") {
      blok.remove();
    } else if (actie === "bron") {
      naarBron(blok);
      return;                       // de pas zou het bewerkvlak meteen weer inpakken
    } else if (actie === "type") {
      // HETZELFDE MENU ALS DE SCHUINE STREEP, op een blok dat al inhoud heeft. Dezelfde tabel van
      // de server, dezelfde uitvoerpaden; alleen het blok waarop hij werkt is niet leeg.
      blokMenuOpen(blok, body);
      return;                       // het menu doet de rest; normaliseren komt daarna
    }
    NV.blokNormaliseer(body);
  }

  // DOM → RUWE MARKDOWN, en alleen voor deze twee soorten. Dit is de ENIGE plek waar de browser
  // iets van het markdown-formaat weet, en dat is bewust zo klein gehouden: een tabel is
  // pipe-gescheiden en een codeblok staat tussen hekken. De weg terug — van tekst naar een blok —
  // doet de SERVER bij het opslaan, zoals overal. Er komt geen tweede renderer in JS.
  function blokBron(blok) {
    // OP DE BLOKSOORT, NIET OP DE TAG. `data-blok` is wat de server zegt dat dit blok is; welke
    // tag daarbij hoort staat in `BLOK_SOORTEN` en hoort hier niet nóg een keer te staan — dat
    // is precies wat `test_javascript_draagt_geen_eigen_soorten_lijst` bewaakt.
    var inhoud = blok.firstElementChild;
    while (inhoud && inhoud.hasAttribute && inhoud.hasAttribute("data-chrome")) {
      inhoud = inhoud.nextElementSibling;
    }
    if (!inhoud) return "";
    if (blok.dataset.blok === "tabel") {
      var uit = [];
      Array.prototype.forEach.call(inhoud.querySelectorAll("tr"), function (tr, i) {
        var cellen = Array.prototype.map.call(tr.children, function (c) {
          return (c.textContent || "").trim();
        });
        uit.push("| " + cellen.join(" | ") + " |");
        if (i === 0) uit.push("|" + Array(cellen.length + 1).join("---|"));
      });
      return uit.join("\n");
    }
    if (blok.dataset.blok === "code") {
      var taal = inhoud.getAttribute("data-taal") || "";
      return "```" + taal + "\n" + (inhoud.textContent || "") + "\n```";
    }
    return "";
  }

  function naarBron(blok) {
    var bron = blokBron(blok);
    if (!bron) return;
    // DEZELFDE UITLEG ALS BIJ EEN NIEUWE TABEL (26 september 2026). Hij kwam alleen mee op de
    // menu-route, dus wie een BESTAANDE tabel openmaakte kreeg dezelfde `|---|---|`-val zonder
    // waarschuwing. De server hangt hem sinds deze stap aan het blok zelf (`_md`), dus hier hoeft
    // alleen doorgegeven te worden wat er al staat.
    //
    // DIT BESTAND WEET NOG STEEDS NIET WELK BLOKTYPE UITLEG VERDIENT — het leest een attribuut,
    // net als bij de soorten-tabel. Zou hier `=== "tabel"` staan, dan woonde het vocabulaire op
    // een tweede plek; dat is precies wat `test_javascript_draagt_geen_eigen_soorten_lijst`
    // verbiedt.
    bronVeld(blok, bron, blok.dataset.wikiHint || "");
  }

  /* HET BRON-BEWERKVLAK, los van waar de tekst vandaan komt. Bij "bewerk als tekst" is dat de
   * bestaande inhoud van het blok; bij een NIEUWE tabel of codeblok uit het menu is het een
   * sjabloon dat de server meestuurde. Eén functie, want het is één ding: een blok waarvan je de
   * ruwe markdown bewerkt omdat `contenteditable` er niet mee overweg kan. */
  function bronVeld(blok, tekst, hint) {
    Array.prototype.forEach.call(blok.children, function (k) {
      if (!k.hasAttribute || !k.hasAttribute("data-chrome")) k.remove();
    });
    // Ook de kale tekstknooppunten weg (de `/` van het menu staat er als los knooppunt in).
    Array.prototype.slice.call(blok.childNodes).forEach(function (k) {
      if (k.nodeType === 3) k.remove();
    });
    var veld = document.createElement("textarea");
    veld.className = "wb-bron";
    veld.setAttribute("data-blok-bron", "");
    veld.value = tekst;
    veld.rows = tekst.split("\n").length + 1;
    blok.appendChild(veld);
    // DE UITLEG BIJ HET SJABLOON (26 september 2026). Een leeg tekstvak met `| A | B |` erin zegt
    // niet dat de `|---|---|`-regel er precies zo moet blijven staan — haal je hem weg, dan is het
    // geen tabel meer maar drie regels tekst met streepjes.
    //
    // `data-chrome`, want hij hoort bij het SCHERM en niet bij de tekst: zonder dat zou hij bij
    // het opslaan in de bron belanden, en dan staat de uitleg voortaan in de tabel. Dezelfde
    // verdediging als bij de greep en het bijschrift van een afbeelding.
    //
    // DE TEKST KOMT VAN DE SERVER (`BLOK_HINT`), zoals het sjabloon ernaast. Dit bestand bedenkt
    // geen uitleg, net zomin als het bloktypes bedenkt.
    if (hint) {
      var uitleg = document.createElement("div");
      uitleg.className = "muted wiki-hint";
      uitleg.setAttribute("data-chrome", "");
      uitleg.textContent = hint;
      blok.appendChild(uitleg);
    }
    veld.focus();
  }

  // De grepen aan- of uitzetten. Ze bestaan alleen tijdens het bewerken: een greep op een pagina
  // die je alleen leest, belooft iets dat niet kan.
  function grepen(body, aan) {
    // ALLEEN DE EIGEN GREPEN, niet alle chrome. Dit stond op `[data-chrome]` en haalde daarmee
    // ook het icoon en het herkomst-label van een embed-kaart weg: zodra je "Edit page" klikte,
    // stond die kaart er kaal bij. Geen dataverlies — de server rendert ze bij het herladen weer
    // — maar wel een kaart die er tijdens het bewerken anders uitziet dan erna. Gezien in de
    // browser, niet in een toets.
    //
    // De verdediging die chrome BUITEN DE OPSLAG houdt blijft wél op `[data-chrome]` staan: die
    // zit in de submit-handler, en daar hoort hij ook.
    body.querySelectorAll(".wb-greep").forEach(function (g) { g.remove(); });
    if (!aan) return;
    body.querySelectorAll(":scope > .wb").forEach(function (blok, i) {
      blok.setAttribute("data-blok-id", "b" + i);
      blok.insertBefore(greepVoor(blok), blok.firstChild);
    });
    NV.sleep(body, {
      kaart: ".wb[data-blok-id]", id: "data-blok-id",
      greep: ".wb-greep-knop",
      doel: ".wb[data-blok-id]", naar: "data-blok-id",
      // TOON DE KANT TIJDENS HET SLEPEN. `onDrop` hieronder rekent vóór/ná uit op de
      // muispositie; zonder deze stand gebeurde dat pas bij het loslaten en zag je tot dat
      // moment niet waar je terechtkwam.
      helft: true,
      onDrop: function (id, naar, e) {
        var bron = body.querySelector(".wb[data-blok-id='" + id + "']");
        var doel = body.querySelector(".wb[data-blok-id='" + naar + "']");
        if (!bron || !doel || bron === doel) return;
        // VÓÓR OF NÁ, naar waar je losliet. Alleen "op dit blok" laat je niet kiezen tussen
        // boven en onder, en dan kun je nooit naar de laatste plek slepen.
        var m = doel.getBoundingClientRect();
        body.insertBefore(bron, e.clientY < m.top + m.height / 2 ? doel : doel.nextSibling);
        NV.blokNormaliseer(body);
        grepen(body, true);             // de id's opnieuw nummeren na de verplaatsing
      }
    });
  }

  /* ── Het /-menu: een blok invoegen waar je staat (brok 3, stap 3) ────────────────────────
   *
   * Typ een schuine streep in een LEEG blok en de lijst bloktypes verschijnt eronder. Alleen in
   * een leeg blok: een `/` midden in een zin is een schuine streep, geen commando — dat is het
   * verschil tussen een sneltoets en een val.
   *
   * DE LIJST KOMT VAN DE SERVER (`#wb-menu-sjabloon`). Hier staan geen bloktypes, geen labels en
   * geen commando's: dit bestand kloont het sjabloon en voert uit wat erin staat. Een eigen
   * lijst zou de derde plek zijn waar het vocabulaire woont, en de enige zonder test.
   */
  // Het tekstknooppunt dat ALLEEN de schuine streep bevat — de chrome overslaand, want de greep
  // hangt in hetzelfde blok en bevat ook tekst. Het menu gaat alleen open als een blok precies
  // "/" bevat, dus er is er hooguit één.
  function streepNode(waar) {
    var w = document.createTreeWalker(waar, NodeFilter.SHOW_TEXT, null);
    var n;
    while ((n = w.nextNode())) {
      if (n.parentNode && n.parentNode.closest("[data-chrome]")) continue;
      if (n.textContent.trim() === "/") return n;
    }
    return null;
  }

  /* EEN BESTAND OP DE PLEK VAN DE `+` (26 september 2026).
   *
   * Hiervoor stond er één uploadformulier onderaan de pagina en plakte de server de regel
   * ACHTER de body. Twee dingen klopten daar niet. Je kon een afbeelding niet tussen twee
   * alinea's krijgen zonder hem daarna te verslepen — en erger: het formulier werd ingediend
   * terwijl je middenin een bewerksessie zat, dus de server schreef in de OPGESLAGEN body en
   * stuurde je door, waarmee alles wat je sinds "Edit page" had getypt verdween.
   *
   * DE SERVER RENDERT, DE BROWSER ZET NEER. `d.html` is de uitkomst van dezelfde `_md` die de
   * pagina tekent, één blok groot. Dit bestand leert dus NIET wat een afbeeldingsextensie is of
   * hoe een `![...]` eruitziet — precies de regel die hier al drie keer staat: er komt geen
   * tweede renderer in JS.
   *
   * HET BESTAND IS AL OPGESLAGEN als dit terugkomt. Slaat de schrijver zijn bewerking niet op,
   * dan blijft er een ongebruikt bestand achter. Dat is schijfruimte; andersom (de regel wel, het
   * bestand niet) zou een kapotte afbeelding op de pagina zijn.
   */
  function uploadInBlok(blok, body, accept) {
    var form = document.querySelector("#wiki-form");
    if (!form) return;
    function veld(naam) {
      var el = form.querySelector("[name=" + naam + "]");
      return el ? el.value || "" : "";
    }
    // FAIL-SOFT, ZICHTBAAR MAAR RUSTIG — zelfde lijn als de stickerzoeker. `data-chrome` zodat
    // een melding nooit als tekst in de pagina belandt; de opslag-pas haalt hem eruit.
    function zeg(tekst) {
      blok.innerHTML = "<span class='muted' data-chrome>" + tekst + "</span>";
    }
    var kiezer = document.createElement("input");
    kiezer.type = "file";
    kiezer.accept = accept;
    kiezer.hidden = true;
    document.body.appendChild(kiezer);
    kiezer.addEventListener("change", function () {
      var bestand = kiezer.files && kiezer.files[0];
      kiezer.remove();
      if (!bestand) { zeg("No file chosen."); return; }
      var fd = new FormData();
      fd.append("csrf", veld("csrf"));
      fd.append("aid", veld("aid"));
      fd.append("action", "wiki_bijlage");
      fd.append("mode", "blok");
      fd.append("file", bestand);
      zeg("Uploading…");
      fetch("/action", { method: "POST", body: fd, credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (d) {
          var houder = document.createElement("div");
          houder.innerHTML = d.html || "";
          var nieuw = houder.firstElementChild;
          if (!nieuw || !blok.parentNode) { zeg("Upload failed."); return; }
          blok.parentNode.replaceChild(nieuw, blok);
          NV.blokNormaliseer(body);
          grepen(body, true);
        })
        .catch(function (status) {
          zeg("Upload failed (" + status + "). The file was not added.");
        });
    });
    // OOK ALS DE KIEZER WORDT WEGGEKLIKT blijft het lege blok staan — dat is precies wat je
    // overhoudt als je in een leeg blok een `/` typt en niets kiest, dus geen eigen opruiming.
    kiezer.click();
  }

  /* DE INHOUD WAAROP HET COMMANDO WERKT.
   *
   * Bij de `/`-weg is dat het tekstknooppunt met de streep erin; bij "wijzig type" op een
   * bestaand blok is het de inhoud die er al staat. `execCommand` werkt op de SELECTIE, dus
   * zonder iets te selecteren gebeurt er niets — gemeten bij de streep, en bij een bestaand blok
   * geldt hetzelfde.
   *
   * DE CHROME BLIJFT ERBUITEN. De greep en zijn menu hangen ín het blok; zou je die meeselecteren,
   * dan maakt `formatBlock` er een kop van mét het greep-icoon erin.
   */
  function kiesInhoud(blok) {
    var streep = streepNode(blok);
    if (streep) return { knoop: streep, streep: true };
    var k = blok.firstElementChild;
    while (k && k.hasAttribute && k.hasAttribute("data-chrome")) k = k.nextElementSibling;
    return { knoop: k || blok, streep: false };
  }

  function blokMenuKies(blok, knop, body) {
    // DE STREEP BLIJFT STAAN TÓT NA HET COMMANDO, en dat is niet de volgorde die je zou kiezen.
    // Gemeten: eerst leegmaken en dán `formatBlock` doet NIETS — een leeg blok met een
    // samengevallen selectie heeft geen inhoud om op te werken, dus het bloktype veranderde
    // niet. Het commando krijgt dus de streep als inhoud, en daarna halen we hem weg.
    var doelwit = kiesInhoud(blok);
    var n = doelwit.knoop;
    if (!n) return;
    // TABEL EN CODEBLOK LOPEN NIET LANGS `execCommand`. Ze krijgen hun markdown-sjabloon van de
    // server mee en openen meteen het bron-bewerkvlak; de server maakt er bij het opslaan het
    // echte blok van. Zo blijft er één renderer, en kent dit bestand nog steeds geen bloktypes.
    if (knop.dataset.wikiCmd === "bron") {
      bronVeld(blok, knop.dataset.wikiArg || "", knop.dataset.wikiHint || "");
      NV.blokNormaliseer(body);
      grepen(body, true);
      return;
    }
    // AFBEELDING EN BESTAND OPENEN EEN BESTANDSKIEZER. De derde soort menu-item, naast "de
    // browser maakt het blok" (execCommand) en "de server levert een sjabloon" (bron).
    if (knop.dataset.wikiCmd === "upload") {
      uploadInBlok(blok, body, knop.dataset.wikiArg || "");
      return;
    }
    var r = document.createRange();
    r.selectNodeContents(n);
    var s = getSelection();
    s.removeAllRanges();
    s.addRange(r);
    body.focus();
    try { document.execCommand("styleWithCSS", false, false); } catch (e) { /* oud */ }
    document.execCommand(knop.dataset.wikiCmd, false, knop.dataset.wikiArg || undefined);
    // OPNIEUW ZOEKEN, niet `n` hergebruiken. Gemeten: `formatBlock` bouwt het element opnieuw op
    // en het oude tekstknooppunt is daarna losgekoppeld — de streep bleef dan gewoon staan in
    // het nieuwe blok. Het menu gaat alleen open bij een blok dat precies "/" is, dus er is er
    // hooguit één te vinden.
    var streep = streepNode(body);
    if (streep) streep.remove();
    NV.blokNormaliseer(body);
    grepen(body, true);
  }

  /* DE TEKST VAN EEN BLOK, ZONDER DE CHROME. Gemeten in de browser en niet voorzien: de greep
   * hangt ÍN het blok, dus `blok.textContent` bevat ook zijn menu-labels —
   * "↑ omhoog↓ omlaag✕ verwijderen". Elk blok leek daardoor gevuld, en de /-lus hieronder kon
   * nooit aanslaan. Het opslaan liep hier niet op stuk (de grepen gaan er eerst uit, en de
   * server negeert `data-chrome`), maar alles wat de tekst van een blok LEEST wel. */
  function blokTekst(blok) {
    var k = blok.cloneNode(true);
    k.querySelectorAll("[data-chrome]").forEach(function (g) { g.remove(); });
    return (k.textContent || "").trim();
  }

  /* HET BLOKTYPE-MENU, \u00c9\u00c9N KEER \u2014 voor de schuine streep \u00e9n voor de greep (26 september 2026).
   *
   * Hij hing in `blokMenu`, waar alleen de `/`-weg bij kon. De greep kreeg daardoor geen "wijzig
   * type": een blok dat er al stond kon je verplaatsen en verwijderen, maar niet omzetten \u2014 je
   * moest de tekst knippen, het blok weggooien, een nieuw blok maken en plakken.
   *
   * \u00c9\u00c9N MENU TEGELIJK, en daarom staat `openMenu` hier en niet in een closure per aanroeper.
   * Twee open menu's laten je raden bij welk blok je bezig bent.
   */
  var openMenu = null;

  function sluitBlokMenu() {
    if (openMenu) { openMenu.remove(); openMenu = null; }
  }

  function blokMenuOpen(blok, body) {
    var sjabloon = document.getElementById("wb-menu-sjabloon");
    if (!sjabloon || !blok) return;
    sluitBlokMenu();
    var menu = sjabloon.cloneNode(true);
    menu.removeAttribute("id");
    menu.hidden = false;
    menu.addEventListener("click", function (e) {
      var knop = e.target.closest("[data-wiki-cmd]");
      if (!knop) return;
      e.preventDefault();
      var doel = blok;
      sluitBlokMenu();
      blokMenuKies(doel, knop, body);
    });
    blok.appendChild(menu);
    openMenu = menu;
    // ZWEVEN IN PLAATS VAN HANGEN (26 september 2026). Hiervoor zette `appendChild` hem waar het
    // blok toevallig stond, met `position:absolute` eronder: op een lange pagina viel het menu
    // daarmee onder de vouw, en dan kies je uit een lijst die je niet ziet.
    //
    // `zweefBij` IS DEZELFDE POSITIONEERDER als die van de opmaakbalk en de link-kaart: eerst
    // erboven, anders eronder, altijd binnen het scherm. Een derde implementatie zou betekenen
    // dat het ene ding na een wijziging anders zweeft dan het andere.
    zweefBij(menu, blok.getBoundingClientRect());
  }

  function blokMenu(body) {
    if (!document.getElementById("wb-menu-sjabloon")) return;

    body.addEventListener("input", function () {
      var blok = getSelection().anchorNode;
      blok = blok && (blok.nodeType === 1 ? blok : blok.parentNode);
      blok = blok && blok.closest ? blok.closest(".wb") : null;
      sluitBlokMenu();
      if (!blok || blokTekst(blok) !== "/") return;
      blokMenuOpen(blok, body);
    });

    body.addEventListener("keydown", function (e) {
      if (e.key === "Escape") sluitBlokMenu();
    });
  }

  /* ZWEVEN BIJ EEN PLEK OP HET SCHERM — ÉÉN implementatie voor twee dingen (26 september 2026).
   *
   * De opmaak-werkbalk hangt bij je selectie, de link-kaart bij de link waar je op klikt. Dat is
   * hetzelfde probleem: zet dit element vlak bij dat vak, en laat het niet half buiten beeld
   * hangen. Een tweede implementatie zou betekenen dat de ene na een wijziging anders zweeft dan
   * de andere — precies de reden die boven `NV.sleep` staat voor hétzelfde soort hergebruik.
   *
   * EERST TONEN, DAN METEN. Een verborgen element heeft geen maat, dus andersom rekent hij met
   * hoogte 0 en landt het kaartje pal op de tekst.
   */
  function zweefBij(el, vak) {
    el.hidden = false;
    var eigen = el.getBoundingClientRect();
    var marge = 8;
    // ERBOVEN, EN ANDERS ERONDER. Bovenin het scherm past er niets boven; dan zou het half buiten
    // beeld hangen. Eronder is de enige plek die dan overblijft, en dat is wat elke editor doet.
    var top = vak.top - eigen.height - marge;
    if (top < marge) top = vak.bottom + marge;
    // EN BINNEN HET VENSTER HOUDEN. Iets helemaal onderaan zou het eronder duwen; iets ver naar
    // rechts zou het over de rand schuiven.
    var max = window.innerHeight - eigen.height - marge;
    if (top > max) top = Math.max(marge, max);
    var links = vak.left;
    var rechts = window.innerWidth - eigen.width - marge;
    if (links > rechts) links = rechts;
    if (links < marge) links = marge;
    el.style.top = Math.round(top) + "px";
    el.style.left = Math.round(links) + "px";
  }

  /* BEWERKEN IS DE STAND, NIET EEN MODUS (26 september 2026).
   *
   * Hiervoor stond een pagina read-only tot je op "Edit page" klikte. Dat is niet hoe een
   * tekstverwerker werkt: daar open je een document en typ je erin. De knop is weg; wie mag
   * bewerken krijgt een bewerkbare pagina zodra hij hem opent.
   *
   * DE POORT VERSCHUIFT NIET. Er is hier geen `can_edit`-tak: `_wiki_editor` rendert zonder
   * bewerkrecht géén `#wiki-form`, en zonder dat formulier valt deze functie meteen terug. De
   * server beslist dus nog steeds wie mag, op precies één plek.
   *
   * OPSLAAN BLIJFT EXPLICIET \u2014 geen autosave per toetsaanslag. De opslaan-balk verschijnt pas als
   * er echt iets veranderd is; zie `gewijzigd()`.
   */
  function wikiEdit(root) {
    var body = root.querySelector("#wiki-body");
    var titel = root.querySelector("#wiki-titel");
    var form = root.querySelector("#wiki-form");
    var tb = root.querySelector("#wiki-tb");
    var kaart = root.querySelector("#wiki-linkkaart");
    // OP DE BODY GEHAAKT en niet meer op de startknop, want die bestaat niet meer. `#wiki-form`
    // is de poort: geen formulier = geen bewerkrecht = niets aanzetten.
    if (!body || !titel || !form || body.dataset.nvWired) return;
    body.dataset.nvWired = "1";

    var origineel = { body: body.innerHTML, titel: titel.textContent };
    var bezig = false;
    blokMenu(body);

    function editeerbaar(aan) {
      body.contentEditable = aan ? "true" : "false";
      // `plaintext-only` houdt opmaak UIT de titel; een titel met een vetgedrukt woord erin is
      // geen titel maar een zin. Niet elke browser kent de waarde — dan valt hij terug op
      // gewoon bewerkbaar, en de server neemt toch alleen de tekst.
      titel.contentEditable = aan ? "plaintext-only" : "false";
      if (aan && titel.contentEditable !== "plaintext-only") titel.contentEditable = "true";
      body.classList.toggle("wiki-aan", aan);
      titel.classList.toggle("wiki-aan", aan);
      grepen(body, aan);
      // DE WERKBALK VOLGT DE SELECTIE, NIET DE STAND (26 september 2026). Hier stond
      // `tb.hidden = !aan`, en dat klopte toen bewerken een modus was. Als stand betekende het:
      // een vaste balk op elke pagina, altijd — die bovendien wegscrolde zodra je ver genoeg naar
      // beneden was. Zie `balkBijSelectie` hieronder.
      if (tb && !aan) tb.hidden = true;
      bezig = aan;
    }

    /* DE LINK-KAART — het Docs/Notion-gedrag bij een klik op een link (26 september 2026).
     *
     * IN EEN BEWERKBAAR VELD BRENGT EEN KLIK OP EEN LINK JE NERGENS HEEN: `contenteditable` vangt
     * hem af en zet de cursor erin. Je ziet dus een link, je klikt erop, en er gebeurt niets —
     * en het adres zelf zie je nergens, want dat zit in het `href`-attribuut.
     *
     * HET KAARTJE TOONT HET ADRES en de drie dingen die je ermee kunt. `Open` omdat de klik dat
     * niet meer doet, `Edit` omdat een adres wijzigen anders betekent: weghalen en opnieuw maken,
     * en `Remove` omdat je een link zonder dat nooit meer kwijtraakt.
     *
     * CMD/CTRL-KLIK EN DE MIDDELSTE KNOP NAVIGEREN DIRECT, zoals overal elders op het web. Wie
     * die gewoonte heeft, hoort er niet op een kaartje te stuiten.
     */
    var huidigeLink = null;

    function kaartWeg() {
      if (!kaart || kaart.hidden) return;
      kaart.hidden = true;
      huidigeLink = null;
      toonAdresveld(false);
    }

    function toonAdresveld(aan) {
      if (!kaart) return;
      var tekst = kaart.querySelector(".wiki-linkurl");
      var veld = kaart.querySelector(".wiki-linkveld");
      if (tekst) tekst.hidden = aan;
      if (veld) veld.hidden = !aan;
    }

    /* EEN ADRES ZONDER SCHEMA IS GEEN LINK VOOR DE SERVER. `_md` en de weg terug eisen allebei
     * `http(s)://` of ons eigen bestandspad; wie "nooch.earth" typt krijgt van de browser een
     * RELATIEVE href, en die valt er bij het opslaan stil uit — de tekst blijft staan, de link
     * verdwijnt. Vandaar dat hier een schema bij komt in plaats van dat het later misgaat. */
    function heelAdres(ruw) {
      var a = (ruw || "").trim();
      if (!a) return "";
      if (/^https?:\/\//i.test(a) || a.indexOf("/wiki-bestand/") === 0) return a;
      if (/^[a-z][a-z0-9+.-]*:/i.test(a)) return "";      // javascript:, data:, mailto: → fail closed
      return "https://" + a;
    }

    function linkVan(knoop) {
      if (!knoop) return null;
      var el = knoop.nodeType === 3 ? knoop.parentNode : knoop;
      if (!el || !el.closest) return null;
      var a = el.closest("a");
      return a && body.contains(a) ? a : null;
    }

    function toonKaart(a, bewerken) {
      if (!kaart || !a) return;
      huidigeLink = a;
      var tekst = kaart.querySelector(".wiki-linkurl");
      var veld = kaart.querySelector(".wiki-linkveld");
      var adres = a.getAttribute("href") || "";
      if (tekst) { tekst.textContent = adres || "(no address yet)"; tekst.href = adres || "#"; }
      if (veld) veld.value = adres;
      toonAdresveld(!!bewerken);
      zweefBij(kaart, a.getBoundingClientRect());
      if (bewerken && veld) veld.focus();
    }

    function bewaarAdres() {
      var veld = kaart && kaart.querySelector(".wiki-linkveld");
      if (!veld || !huidigeLink) return;
      var adres = heelAdres(veld.value);
      if (!adres) { kaartWeg(); return; }
      huidigeLink.setAttribute("href", adres);
      huidigeLink.setAttribute("target", "_blank");
      huidigeLink.setAttribute("rel", "noopener");
      toonKaart(huidigeLink, false);
      NV.blokNormaliseer(body);
      grepen(body, true);
    }

    function haalLinkWeg() {
      if (!huidigeLink) return;
      // DE SELECTIE EERST OP DE LINK, want `unlink` werkt op wat er geselecteerd is. Zonder dit
      // haalt hij de link weg waar de cursor toevallig stond — of geen enkele.
      var r = document.createRange();
      r.selectNodeContents(huidigeLink);
      var sel = getSelection();
      sel.removeAllRanges();
      sel.addRange(r);
      document.execCommand("unlink");
      kaartWeg();
      NV.blokNormaliseer(body);
      grepen(body, true);
    }

    if (kaart) {
      kaart.addEventListener("mousedown", function (e) { e.preventDefault(); });  // focus blijft
      kaart.addEventListener("click", function (e) {
        var knop = e.target.closest("[data-link-actie]");
        if (!knop || !huidigeLink) return;
        var actie = knop.dataset.linkActie;
        if (actie === "open") {
          var adres = huidigeLink.getAttribute("href");
          if (adres) window.open(adres, "_blank", "noopener");
          kaartWeg();
        } else if (actie === "edit") {
          toonKaart(huidigeLink, true);
        } else if (actie === "remove") {
          haalLinkWeg();
        }
      });
      var veld = kaart.querySelector(".wiki-linkveld");
      if (veld) {
        veld.addEventListener("keydown", function (e) {
          if (e.key === "Enter") { e.preventDefault(); bewaarAdres(); }
          else if (e.key === "Escape") { e.preventDefault(); kaartWeg(); }
        });
        veld.addEventListener("blur", bewaarAdres);
      }
    }

    // EEN KLIK OP EEN LINK. `mousedown` voor de middelste knop (die geeft geen `click`), `click`
    // voor de rest — anders mist de middelste-knop-gewoonte hier precies.
    body.addEventListener("click", function (e) {
      var a = linkVan(e.target);
      if (!a) { if (!kaart || !kaart.contains(e.target)) kaartWeg(); return; }
      if (e.metaKey || e.ctrlKey) return;      // direct navigeren, zoals overal elders
      e.preventDefault();
      toonKaart(a, false);
    });
    body.addEventListener("auxclick", function (e) {
      if (e.button !== 1) return;              // alleen de middelste knop
      var a = linkVan(e.target);
      if (!a) return;
      var adres = a.getAttribute("href");
      if (adres) window.open(adres, "_blank", "noopener");
    });

    /* DE OPMAAK-BALK ZWEEFT BIJ JE SELECTIE (26 september 2026).
     *
     * Hiervoor was het een vaste balk boven het bewerkvlak (`position:sticky`). Twee problemen,
     * en het tweede kwam er pas bij toen bewerken de stand werd: op een lange pagina scrolde hij
     * weg zodra je ver genoeg naar beneden was, en sindsdien stond hij bovendien op élke pagina
     * permanent in beeld terwijl je alleen aan het lezen was.
     *
     * Een balkje dat bij je selectie verschijnt, lost dat STRUCTUREEL op: er is geen vaste balk
     * meer om weg te scrollen. Hij komt waar je hem nodig hebt en gaat weer weg.
     *
     * ALLEEN BIJ EEN ECHTE SELECTIE. Een samengevallen selectie is een gewone cursor, en daar valt
     * niets op te maken — een balkje dat dan verschijnt, springt bij elke klik in beeld.
     *
     * BINNEN DIT BEWERKVLAK. Er kan meer dan één bewerkbaar ding op een scherm staan (de titel
     * heeft ook `contenteditable`); een selectie daarbuiten gaat deze balk niet aan.
     */
    function balkWeg() {
      if (tb && !tb.hidden) tb.hidden = true;
    }

    // DE KAART SCHUIFT MEE, of verdwijnt als de link het beeld uit is. Zelfde reden als bij de
    // balk: de positie staat in venstercoördinaten.
    function kaartBijScroll() {
      if (!kaart || kaart.hidden || !huidigeLink || !body.contains(huidigeLink)) return kaartWeg();
      var vak = huidigeLink.getBoundingClientRect();
      if (vak.bottom < 0 || vak.top > window.innerHeight) return kaartWeg();
      zweefBij(kaart, vak);
    }
    window.addEventListener("scroll", kaartBijScroll, true);
    window.addEventListener("resize", kaartBijScroll);

    function balkBijSelectie() {
      if (!tb || !bezig) return;
      var sel = window.getSelection();
      if (!sel || !sel.rangeCount || sel.isCollapsed) return balkWeg();
      var r = sel.getRangeAt(0);
      // `commonAncestorContainer` KAN EEN TEKSTKNOOPPUNT ZIJN, en die heeft geen `closest`.
      var knoop = r.commonAncestorContainer;
      if (knoop.nodeType === 3) knoop = knoop.parentNode;
      if (!knoop || !body.contains(knoop)) return balkWeg();
      var vak = r.getBoundingClientRect();
      // EEN SELECTIE MET BREEDTE NUL KOMT ECHT VOOR: direct na een `execCommand` is de range
      // heropgebouwd en meet hij even niets. Dan is er niets om boven te hangen.
      if (!vak.width && !vak.height) return balkWeg();

      zweefBij(tb, vak);
    }

    // OP `selectionchange` VAN HET DOCUMENT, want een selectie is geen gebeurtenis van één
    // element: hij ontstaat met de muis, met shift+pijltjes, met dubbelklik en met ctrl+A, en
    // alleen dit ene event vangt ze allemaal.
    document.addEventListener("selectionchange", balkBijSelectie);
    // MEEBEWEGEN BIJ SCROLLEN. De positie is in venstercoördinaten, dus zonder dit blijft de balk
    // staan waar hij stond terwijl de tekst eronder wegschuift. `balkBijSelectie` rekent hem
    // opnieuw uit en verbergt hem als de selectie het beeld uit is.
    window.addEventListener("scroll", balkBijSelectie, true);
    window.addEventListener("resize", balkBijSelectie);
    // FOCUS WEG UIT HET VELD = BALK WEG. `focusout` en niet `blur`, want de balk zelf zit buiten
    // het bewerkvlak; een klik op een knop verplaatst de focus en mag hem niet meteen sluiten.
    // De knoppen houden de focus tegen met `mousedown`/`preventDefault` (zie hieronder), dus wie
    // hier belandt, klikte ergens anders.
    body.addEventListener("focusout", function (e) {
      if (tb && tb.contains(e.relatedTarget)) return;
      balkWeg();
      // DE KAART BLIJFT ALS JE ER NAARTOE KLIKT, anders sluit hij op het moment dat je hem
      // gebruikt — dezelfde uitzondering als bij de werkbalk hierboven.
      if (!kaart || !kaart.contains(e.relatedTarget)) kaartWeg();
    });

    /* DE OPSLAAN-BALK KOMT PAS ALS ER IETS TE BEWAREN IS.
     *
     * Altijd tonen zou onder elke pagina een balk met "Save" en een uitlegzin zetten, ook als je
     * alleen aan het lezen bent. Pas tonen bij een wijziging houdt de pagina rustig én laat
     * opslaan een expliciete handeling — er wordt niets vanzelf bewaard.
     *
     * EEN MutationObserver EN GEEN LIJST AANROEPPUNTEN. Er zijn minstens acht plekken die het
     * document veranderen (typen, plakken, de werkbalk, het blokmenu, een upload, slepen,
     * omhoog/omlaag, verwijderen) en één vergeten aanroep betekent: iemand bewerkt, ziet geen
     * knop, en verliest zijn werk. De waarnemer hangt aan de boom zelf en kan er dus geen missen.
     *
     * HIJ START NÁ `editeerbaar(true)`, want het aanzetten hangt zelf de grepen en de plus in de
     * blokken — dat zijn chrome-mutaties, geen bewerkingen.
     */
    function gewijzigd() {
      if (form.hidden) form.hidden = false;
    }

    editeerbaar(true);
    form.hidden = true;
    var waarnemer = new MutationObserver(gewijzigd);
    waarnemer.observe(body, {
      childList: true, subtree: true, characterData: true, attributes: true
    });
    titel.addEventListener("input", gewijzigd);

    var annuleer = form.querySelector("[data-wiki-cancel]");
    if (annuleer) annuleer.addEventListener("click", function () {
      body.innerHTML = origineel.body;
      titel.textContent = origineel.titel;
      // TERUG NAAR DE BEGINSTAND, NIET NAAR READ-ONLY. Annuleren gooit je wijzigingen weg; het
      // ontneemt je niet het recht om te bewerken, want dat is sinds deze stap de stand.
      grepen(body, true);
      // HET HERSTEL IS ZELF EEN MUTATIE, en de waarnemer draait ASYNCHROON. Gemeten in Firefox:
      // `form.hidden = true` liep eerst, daarna kwam de callback van het terugzetten langs en
      // stond de balk weer open — annuleren leek dan niets te doen. `takeRecords()` leegt de
      // wachtrij van wat er zélf net is teruggezet; alles wat daarna gebeurt telt gewoon weer.
      waarnemer.takeRecords();
      form.hidden = true;
    });

    // De werkbalk. `styleWithCSS=false` is de hele reden dat dit zonder library kan: mét CSS
    // levert de browser `<span style="font-weight:bold">`, en dat is geen tag die de server kent
    // — de vetgedrukte tekst zou dan bij het opslaan gewoon gewone tekst worden.
    if (tb) tb.querySelectorAll("[data-wiki-cmd]").forEach(function (knop) {
      knop.addEventListener("mousedown", function (e) { e.preventDefault(); });  // focus blijft staan
      knop.addEventListener("click", function () {
        try { document.execCommand("styleWithCSS", false, false); } catch (e) { /* oud */ }
        // INLINE CODE IS HET ENIGE ITEM ZONDER BROWSER-COMMANDO. Hier staat dus één `if` en geen
        // tweede mechaniek: `inlineCode()` doet zijn werk en daarna loopt alles hetzelfde door
        // (normaliseren, focus terug).
        if (knop.dataset.wikiCmd === "nvCode") {
          inlineCode();
        } else if (knop.dataset.wikiCmd === "nvLink") {
          // STAAT DE SELECTIE AL IN EEN LINK, dan is dit "laat me dit adres zien en bewerken" —
          // precies wat de kaart doet. Anders is het een NIEUWE link, en dan bestaat er nog geen
          // `<a>` om een kaartje aan op te hangen: eerst er een maken met een leeg adres, dan de
          // kaart in bewerkstand. Zo is er één plek waar een adres wordt ingevuld.
          var sel = getSelection();
          var bestaand = sel && sel.rangeCount ? linkVan(sel.getRangeAt(0).commonAncestorContainer)
                                               : null;
          if (bestaand) {
            toonKaart(bestaand, true);
          } else if (sel && !sel.isCollapsed && sel.toString().trim()) {
            // `createLink` HEEFT EEN HREF NODIG, ook al vullen we hem zo meteen pas echt in: met
            // een lege waarde maakt de browser geen `<a>` en is er niets om aan te wijzen.
            document.execCommand("createLink", false, "#");
            var nieuweLink = sel.rangeCount
              ? linkVan(sel.getRangeAt(0).commonAncestorContainer) : null;
            if (nieuweLink) {
              nieuweLink.setAttribute("href", "");
              toonKaart(nieuweLink, true);
            }
          }
        } else {
          document.execCommand(knop.dataset.wikiCmd, false, knop.dataset.wikiArg || null);
        }
        // Elk van deze commando's laat het blokmodel scheef achter; zie `NV.blokNormaliseer`.
        NV.blokNormaliseer(body);
        body.focus();
      });
    });

    // Plakken gaat als PLATTE TEKST. Wie een stuk uit Word of een website plakt, brengt anders
    // een halve stylesheet mee; de server gooit die toch weg, en dan zie je pas na het opslaan
    // dat je opmaak verdwenen is. Zo zie je meteen wat je krijgt.
    /* ENTER LEVERT METEEN EEN VOLWAARDIG BLOK (26 september 2026).
     *
     * De browser splitst zelf netjes, maar wat hij achterlaat is een KALE tag: geen `.wb`, geen
     * `data-blok`, dus geen greep en niet sleepbaar. Dat bleef zo tot er toevallig iets anders
     * normaliseerde — een werkbalkknop, een blokmenu-keuze — en tot die tijd was de regel die je
     * net had aangemaakt het enige stuk pagina waar de hele bloklaag niet voor gold.
     *
     * NÁ DE SPLITSING, NIET ERVOOR. Op `keydown` bestaat de nieuwe regel nog niet; de pas zou dan
     * het blok normaliseren dat er al stond. Vandaar `setTimeout(0)`: de browser doet zijn ding,
     * daarna ruimen wij op.
     *
     * GEEN NIEUW MECHANISME: `blokNormaliseer` + `grepen` is exact het paar dat elke andere
     * DOM-wijziging hier al afsluit (de werkbalk, het blokmenu, slepen, een upload).
     */
    body.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" || e.shiftKey) return;   // shift+Enter is een regelafbreking, geen blok
      if (e.target.closest && e.target.closest("[data-blok-bron]")) return;  // in een bron-veld
      setTimeout(function () {
        NV.blokNormaliseer(body);
        grepen(body, true);
      }, 0);
    });

    body.addEventListener("paste", function (e) {
      if (!bezig) return;
      e.preventDefault();
      var tekst = (e.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, tekst);
    });

    form.addEventListener("submit", function () {
      // WAT ER OP HET SCHERM STAAT IS WAT ER WORDT OPGESLAGEN. Typen en plakken laten óók blokken
      // scheef achter (Enter in een kop, een alinea die uit elkaar valt); zonder deze pas belandt
      // zo'n kale tag in de POST, en dan is de pagina na het herladen een blok kwijt.
      NV.blokNormaliseer(body);
      // DE GREPEN ERUIT VÓÓR HET UITLEZEN. Dit is de eerste van twee verdedigingen; de tweede
      // staat op de server (`data-chrome` in `_BronParser`). Allebei, want dit is het enige punt
      // waar chrome in de opgeslagen tekst kan lekken.
      body.querySelectorAll("[data-chrome]").forEach(function (g) { g.remove(); });
      body.querySelectorAll("[data-blok-id]").forEach(function (b) { b.removeAttribute("data-blok-id"); });
      // EEN TEXTAREA LIEGT IN innerHTML. Hij geeft daar zijn OORSPRONKELIJKE inhoud terug, niet
      // wat de gebruiker erin typte — dus zonder deze regel wordt elke bewerking van een tabel of
      // codeblok stil weggegooid en staat er na het opslaan weer de oude tekst. Gemeten in de
      // browser, niet bedacht.
      body.querySelectorAll("textarea[data-blok-bron]").forEach(function (t) {
        t.textContent = t.value;
      });
      // EEN VINKJE LIEGT OP DEZELFDE MANIER. Aanvinken verandert de `checked`-PROPERTY, maar
      // `innerHTML` schrijft het ATTRIBUUT — dus zonder deze regel verdampt elk vinkje dat je
      // zet. Precies dezelfde val als de textarea hierboven, en op dezelfde plek opgelost.
      body.querySelectorAll("input[type=checkbox]").forEach(function (v) {
        v.toggleAttribute("checked", v.checked);
      });
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

    // WELKE KNOP "ACTIEF" IS, met twee verschillende beloftes en daarom twee waardes:
    //
    //   aria-current="page"  de server zet dit op het item dat bij het HUIDIGE PAD hoort;
    //   aria-current="true"  dit paneel staat open — het pad verandert daar niet, dus "page"
    //                        zou beweren dat je ergens bent waar je niet bent.
    //
    // De CSS selecteert op `[aria-current]` zonder waarde en ziet dus allebei. Een knop die de
    // server al als pagina markeerde, houdt die markering: `pagina` onthoudt hem.
    function markeer(actief) {
      Array.prototype.forEach.call(knoppen, function (k) {
        var pagina = k.dataset.navPagina === "1";
        if (k === actief) k.setAttribute("aria-current", pagina ? "page" : "true");
        else if (pagina) k.setAttribute("aria-current", "page");
        else k.removeAttribute("aria-current");
      });
    }

    // Onthouden wat de server markeerde, vóór we er zelf aan zitten.
    Array.prototype.forEach.call(knoppen, function (k) {
      if (k.getAttribute("aria-current") === "page") k.dataset.navPagina = "1";
    });

    function sluit() {
      open = null;
      onthoud("");                      // expliciet dicht = ook niet meer herstellen
      paneel.hidden = true;
      document.body.classList.remove("navpaneel-open");
      Array.prototype.forEach.call(knoppen, function (k) {
        k.setAttribute("aria-expanded", "false");
      });
      markeer(null);
    }

    // HET PANEEL OVERLEEFT NU EEN PAGINALAAD (23 september 2026). Tot vandaag leefde "welk paneel
    // staat open" alleen in `open` hierboven, en die begint bij elke navigatie opnieuw op null.
    // Klikken op een rol in de organisatieboom is een gewone link, dus het paneel viel dicht en je
    // moest voor elke volgende rol opnieuw op Organization klikken — precies het doorbladeren
    // waar de boom voor bedoeld is.
    //
    // `sessionStorage` EN NIET DE SERVER: het is een voorkeur van dit tabblad, geen feit over het
    // dorp. Hij hoort niet in de records, niet in een sessie op de server en niet in een
    // querystring die je per ongeluk deelt. Per tab, en weg als het tabblad weg is.
    //
    // Lezen en schrijven mogen allebei gooien (privémodus, geblokkeerde opslag). Dan werkt het
    // paneel gewoon zoals vroeger: open zolang je op de pagina blijft. Nooit een uitzondering die
    // de rest van de navigatie meesleept.
    var BEWAARSLEUTEL = "nv-navpaneel";

    function onthoud(sleutel) {
      try {
        if (sleutel) sessionStorage.setItem(BEWAARSLEUTEL, sleutel);
        else sessionStorage.removeItem(BEWAARSLEUTEL);
      } catch (e) { /* geen opslag: dan is het paneel simpelweg niet blijvend */ }
    }

    function bewaard() {
      try { return sessionStorage.getItem(BEWAARSLEUTEL) || ""; } catch (e) { return ""; }
    }

    function knopVoor(sleutel) {
      return Array.prototype.filter.call(knoppen, function (k) {
        return k.getAttribute("data-nav-paneel") === sleutel;
      })[0] || null;
    }

    // ÉÉN OPEN-IMPLEMENTATIE, gebruikt door de klik én door het herstel na een paginalaad. Twee
    // kopieën zouden betekenen dat een herstelde stand net iets anders is dan een geklikte —
    // en dat merk je pas als er één iets bijkrijgt.
    function openen(sleutel) {
      var knop = knopVoor(sleutel);
      // Een bewaarde sleutel die niet meer bestaat (Circle sinds #576, Projects sinds #575):
      // niets openen, en het geheugen opruimen zodat het niet elke laad opnieuw probeert.
      if (!knop) { onthoud(""); return; }
      open = sleutel;
      onthoud(sleutel);
      Array.prototype.forEach.call(knoppen, function (k) {
        k.setAttribute("aria-expanded", k === knop ? "true" : "false");
      });
      markeer(knop);
      paneel.hidden = false;
      document.body.classList.add("navpaneel-open");
      binnen.innerHTML = "<p class='muted c2-pleeg'>…</p>";
      // De organisatieboom klapt de tak open waar je NU staat. Een fragment weet niet op welke
      // pagina het landt, dus de client geeft het mee — precies wat de oude zijbalk-injectie
      // server-side deed toen de boom nog met elke pagina meekwam. Bij een herstel is dat de
      // node waar je zojuist op klikte, zodat het paneel lijkt te blijven staan terwijl de
      // markering meeschuift.
      var hier = "";
      if (location.pathname === "/node") {
        hier = new URLSearchParams(location.search).get("id") || "";
      }
      return vul("/nav-paneel?p=" + encodeURIComponent(sleutel) +
                 (hier ? "&hier=" + encodeURIComponent(hier) : ""));
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
        openen(sleutel);
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

    // HET HERSTEL, EN ALLEEN WAAR HET PANEEL THUISHOORT. Stond het paneel open toen je
    // wegklikte, dan staat het er op de volgende `/node`-pagina meteen weer — gevuld voor de
    // node waar je net op landde. Dit is de hele reden dat `openen` een eigen functie is: hier
    // gebeurt letterlijk hetzelfde als bij een klik.
    //
    // DE POORT OP HET PAD is de correctie van 23 september 2026. Zonder hem bleef het paneel op
    // ELKE pagina staan — ook op Wiki, Messages, Projects en Admin — en dan hoort het niet meer
    // bij Organization maar bij de hele site. Het is de uitklap VAN EEN HOOFDITEM; op het
    // scherm van een ander hoofditem heeft hij niets te zoeken.
    //
    // De bewaarde waarde blijft bij zo'n uitstapje gewoon staan: `sessionStorage` onthoudt
    // "stond het paneel open", en de PAGINA beslist of dat hier relevant is. Daarom wissen we
    // hem niet bij het weg navigeren — dat zou "ik heb hem dichtgeklikt" en "ik keek even
    // ergens anders" op één hoop gooien, en alleen het eerste hoort te blijven plakken.
    //
    // Komt er ooit een tweede paneel bij, dan hoort deze poort PER PANEEL te worden: het pad
    // waar hij bij hoort is dan niet meer voor iedereen `/node`.
    if (location.pathname === "/node" && bewaard()) openen(bewaard());
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

  // ── Een kleine viering ────────────────────────────────────────────────────────────────────
  // Een tactical meeting afsluiten is het enige moment in dit dorp waarop een groep mensen samen
  // iets AFMAAKT. Dat mag je zien. Verder niets: geen geluid, geen library, en na tweeënhalve
  // seconde is er geen spoor meer van.
  //
  // DRIE DINGEN DIE HET BESCHAAFD HOUDEN:
  //  * het vlaggetje gaat meteen uit de URL, dus een refresh viert niet opnieuw;
  //  * `prefers-reduced-motion` slaat hem helemaal over — voor wie beweging vermijdt is dit
  //    precies het soort ding dat misselijk maakt, en er gaat geen informatie verloren omdat er
  //    geen in zat;
  //  * `pointer-events: none` op de laag, zodat je tijdens die twee seconden gewoon doorklikt.
  function feest(root) {
    if (root !== document) return;                 // een fragment viert niet mee
    var p = new URLSearchParams(location.search);
    if (!p.get("feest")) return;
    p.delete("feest");
    var q = p.toString();
    history.replaceState(null, "", location.pathname + (q ? "?" + q : "") + location.hash);
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    var laag = document.createElement("div");
    laag.className = "feest";
    laag.setAttribute("aria-hidden", "true");      // versiering, geen inhoud
    var kleuren = ["#00FF00", "#1F9D55", "#FFCE2E", "#FF6B5B", "#000000"];
    for (var i = 0; i < 60; i++) {
      var s = document.createElement("i");
      s.style.left = (10 + Math.random() * 80) + "%";
      s.style.background = kleuren[i % kleuren.length];
      s.style.animationDelay = (Math.random() * 0.25) + "s";
      s.style.animationDuration = (1.4 + Math.random() * 0.9) + "s";
      s.style.setProperty("--dx", (Math.random() * 240 - 120) + "px");
      s.style.setProperty("--dr", (Math.random() * 720 - 360) + "deg");
      laag.appendChild(s);
    }
    document.body.appendChild(laag);
    setTimeout(function () { laag.remove(); }, 2600);
  }

  // ── De emoji-kiezer: zoeken, en invoegen in een tekstveld ─────────────────────────────────
  // ZOEKEN STOND IN EEN INLINE-SCRIPT dat alleen op schermen met de project-modal werd
  // meegestuurd (`window.emoFilter` in `_modal_html`). In Messages bestond die functie niet,
  // dus het zoekveld in de reactie-kiezer deed daar al die tijd niets — `oninput` riep een
  // naam aan die er niet was. Hier staat hij één keer, op elke pagina.
  function emoKiezer(root) {
    root.querySelectorAll("[data-emo-zoek]").forEach(function (veld) {
      if (veld.dataset.nvEmo) return;
      veld.dataset.nvEmo = "1";
      veld.addEventListener("input", function () {
        var q = veld.value.trim().toLowerCase();
        // Het doelwit is de KNOP of zijn formulier: onder een bericht zit elke emoji in een
        // eigen <form class='emo-f'>, in de invoerbalk is het een losse <button>. Allebei
        // dragen `data-k` met de zoekwoorden, dus we verbergen wat die draagt.
        veld.parentNode.querySelectorAll("[data-k]").forEach(function (el) {
          var k = el.getAttribute("data-k") || "";
          el.style.display = (!q || k.indexOf(q) > -1) ? "" : "none";
        });
      });
    });
    // Invoegen in het schrijfveld. Geen submit, geen reactie: alleen tekst erbij op de plek
    // waar de cursor staat.
    root.querySelectorAll("[data-emo-invoeg]").forEach(function (knop) {
      if (knop.dataset.nvEmo) return;
      knop.dataset.nvEmo = "1";
      knop.addEventListener("click", function () {
        var veld = document.getElementById(knop.getAttribute("data-emo-invoeg"));
        if (!veld) return;
        var teken = knop.textContent.trim();
        var a = veld.selectionStart, b = veld.selectionEnd;
        veld.value = veld.value.slice(0, a) + teken + veld.value.slice(b);
        veld.focus();
        veld.selectionStart = veld.selectionEnd = a + teken.length;
        veld.dispatchEvent(new Event("input", { bubbles: true }));
        var det = knop.closest("details");
        if (det) det.open = false;                   // gekozen is klaar
      });
    });
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
    feest(root);
    emoKiezer(root);
  };

  if (document.readyState !== "loading") NV.wire(document);
  else document.addEventListener("DOMContentLoaded", function () { NV.wire(document); });
})();
