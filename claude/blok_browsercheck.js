/* BROWSERCHECK VOOR HET BLOKMODEL (brok 3, 22 september 2026)
 *
 * WAAROM DIT BESTAAT. De normaliseerpas, de greep en het /-menu draaien in de browser, en in
 * deze stack is geen JS-testrunner (geen package.json, geen node_modules). Alles wat pytest
 * bewaakt is de BEDRADING; het GEDRAG is alleen met een echte browser te meten. Ik kan er hier
 * maar één besturen — Chrome. Deze snippet doet in elke browser dezelfde metingen, zodat
 * "even handmatig doorlopen" een uitslag oplevert in plaats van een indruk.
 *
 * GEBRUIK: open een wiki-pagina (/pagina?id=NOTE-…) waar je mag bewerken, open de console,
 * plak dit, en lees de tabel. Alles moet ✓ zijn. De pagina wordt NIET opgeslagen — er wordt
 * alleen in het scherm gewerkt; herlaad na afloop en er is niets veranderd.
 */
(function () {
  var b = document.querySelector("#wiki-body");
  if (!b) return console.log("✗ geen #wiki-body — open een /pagina met bewerkrechten");
  var start = document.querySelector("[data-wiki-start]");
  if (!start) return console.log("✗ geen bewerkknop — je mag deze pagina niet bewerken");
  if (b.contentEditable !== "true") start.click();

  var uit = [];
  function zeg(naam, ok, detail) { uit.push({ toets: naam, uitslag: ok ? "✓" : "✗ FOUT", detail: detail || "" }); }
  function tekstZonderChrome(el) {
    var k = el.cloneNode(true);
    k.querySelectorAll("[data-chrome]").forEach(function (g) { g.remove(); });
    return (k.textContent || "").trim();
  }
  function nieuwBlok(inhoud) {
    var d = document.createElement("div");
    d.className = "wb"; d.setAttribute("data-blok", "p");
    d.appendChild(document.createTextNode(inhoud));
    b.appendChild(d);
    return d;
  }
  function kies(blok) {
    var r = document.createRange(); r.selectNodeContents(blok); r.collapse(false);
    var s = getSelection(); s.removeAllRanges(); s.addRange(r); b.focus();
  }

  // 1. de tabel komt van de server
  var soorten = {};
  try { soorten = JSON.parse(b.getAttribute("data-blok-soorten") || "{}"); } catch (e) {}
  // HIER STOND `=== 7`, en dat was een getal dat de sprint drie keer heeft ingehaald: met het
  // codeblok, de tabel en de embed erbij zijn het er tien, en deze check stond dus al op ✗ FOUT
  // voordat iemand er iets aan deed. Precies de "reference, don't copy"-val — een tweede kopie
  // van een feit dat elders woont. Wat deze check WIL weten is of de tabel van de server komt en
  // of de soorten erin zitten die hij hierna gebruikt.
  var nodig = ["h4", "ul", "blockquote"];
  var mist = nodig.filter(function (t) { return !soorten[t]; });
  zeg("soorten-tabel aanwezig", Object.keys(soorten).length > 0 && mist.length === 0,
      Object.keys(soorten).length + " soorten" + (mist.length ? ", mist: " + mist : ""));

  // 2. elk blok heeft een greep, en die telt niet mee als tekst
  var blok0 = b.querySelector(":scope > .wb");
  zeg("greep in elk blok", !!(blok0 && blok0.querySelector(".wb-greep")));
  zeg("greep telt niet als tekst", blok0 && tekstZonderChrome(blok0).indexOf("omhoog") < 0);

  // 3. formatBlock laat een KALE tag achter — en de pas repareert dat
  var t1 = nieuwBlok("proef kop");
  kies(t1);
  try { document.execCommand("styleWithCSS", false, false); } catch (e) {}
  document.execCommand("formatBlock", false, "<h4>");
  var kaalVoor = [].slice.call(b.children).filter(function (e) { return !e.classList.contains("wb"); }).length;
  NV.blokNormaliseer(b);
  var kaalNa = [].slice.call(b.children).filter(function (e) { return !e.classList.contains("wb"); }).length;
  zeg("formatBlock → pas herstelt het omhulsel", kaalNa === 0,
      "kaal voor: " + kaalVoor + ", na: " + kaalNa);
  // DE SOORT ERBIJ, want alleen "er staat geen kale tag meer" is te weinig. Firefox hernoemt het
  // omhulsel in plaats van het te vervangen, en dan is `kaalNa` allang 0 terwijl er nog `p` staat
  // waar `h` hoort. Die stille helft kostte 23 september een fout in de pas.
  var na3 = [].slice.call(b.children).filter(function (e) { return e.textContent.indexOf("proef kop") >= 0; })[0];
  zeg("formatBlock → en de soort klopt", na3 && na3.dataset.blok === "h",
      "werd: " + (na3 && na3.dataset.blok));

  // 4. insertUnorderedList nest erin — de pas corrigeert data-blok
  var t2 = nieuwBlok("proef lijst");
  kies(t2);
  document.execCommand("insertUnorderedList");
  var na2 = [].slice.call(b.children).filter(function (e) { return e.textContent.indexOf("proef lijst") >= 0; })[0];
  var voorSoort = na2 && na2.dataset.blok;
  NV.blokNormaliseer(b);
  na2 = [].slice.call(b.children).filter(function (e) { return e.textContent.indexOf("proef lijst") >= 0; })[0];
  zeg("lijst → pas corrigeert data-blok", na2 && na2.dataset.blok === "ul",
      voorSoort + " → " + (na2 && na2.dataset.blok));

  // 5. het /-menu opent en levert het juiste bloktype
  var t3 = nieuwBlok("/");
  kies(t3);
  b.dispatchEvent(new InputEvent("input", { bubbles: true }));
  var menu = [].slice.call(b.querySelectorAll(".wb-menu")).filter(function (m) { return !m.hidden && !m.id; })[0];
  zeg("/-menu opent", !!menu, menu ? menu.querySelectorAll("[data-wiki-cmd]").length + " opties" : "");
  if (menu) {
    var citaat = [].slice.call(menu.querySelectorAll("[data-wiki-cmd]")).filter(
      function (k) { return k.dataset.wikiArg === "<blockquote>"; })[0];
    if (citaat) {
      citaat.click();
      var laatste = b.children[b.children.length - 1];
      zeg("/-menu maakt een citaat", laatste.dataset.blok === "q", "werd: " + laatste.dataset.blok);
      zeg("de schuine streep is weg", tekstZonderChrome(laatste).indexOf("/") < 0);
      zeg("de greep overleeft het", !!laatste.querySelector(".wb-greep"));
    }
  }

  // 6. de greep gaat eruit vóór het opslaan (we simuleren alleen het uitlezen)
  var kloon = b.cloneNode(true);
  kloon.querySelectorAll("[data-chrome]").forEach(function (g) { g.remove(); });
  zeg("geen chrome in de opgeslagen HTML", kloon.innerHTML.indexOf("wb-greep") < 0);

  // 7. het afgeleide blok (feiten/backlinks): het TOONT, het bewaart niet
  var afg = b.querySelector("[data-blok='facts']");
  zeg("afgeleid blok staat er", !!afg);
  if (afg) {
    // De browser mag de caret hier niet in zetten: wat erin staat is uitvoer die bij elk lezen
    // opnieuw wordt berekend, dus typen erin verdampt bij het opslaan.
    zeg("afgeleid blok is niet bewerkbaar", afg.isContentEditable === false);
    zeg("afgeleid blok draagt zijn bron", afg.getAttribute("data-blok-bron") === "{{facts}}");
    zeg("afgeleid blok heeft een greep", !!afg.querySelector(".wb-greep"));
    // DE VORM DIE STUK WAS: een formulier met een verborgen veld. `<input>` heeft geen eindtag.
    zeg("het formulier staat er ook echt", !!afg.querySelector("input[type='hidden']"));
    // En de pas mag hem niet omdopen tot alinea, zoals hij met een kale <h4> wél doet.
    NV.blokNormaliseer(b);
    zeg("de pas laat het afgeleide blok met rust",
        b.querySelector("[data-blok='facts']") === afg, "soort: " + afg.dataset.blok);
  }

  // 8. SLEPEN — het gebaar zelf, met eigen pointer-events
  //
  // WAAROM DIT ER NIET STOND EN HET WEL MOEST. In het ontwerpdocument van 25 september staat dat
  // er "geen drag-and-drop" is. Slepen werkt al sinds brok 3, ook op prod — maar niets liet dat
  // zien, en geen enkele check probeerde het. De sleep-actie van de browser-extensie stuurt
  // alleen `pointermove`, geen `pointerdown`/`pointerup`, dus daarmee is het gebaar niet uit te
  // voeren. Deze check stuurt ze zelf.
  function pev(t, x, y, doel) {
    (doel || document).dispatchEvent(new PointerEvent(t, {
      bubbles: true, cancelable: true, clientX: x, clientY: y,
      button: 0, buttons: t === "pointerup" ? 0 : 1, pointerType: "mouse", pointerId: 1
    }));
  }
  var rij = function () {
    return [].slice.call(b.querySelectorAll(":scope > .wb"))
             .map(function (x) { return x.dataset.blok; }).join(",");
  };
  var volgordeVoor = rij();
  var eerste = b.querySelector(":scope > .wb");
  var greep = eerste && eerste.querySelector(".wb-greep-knop");
  var doelBlok = [].slice.call(b.querySelectorAll(":scope > .wb"))[3];
  if (!greep || !doelBlok) {
    zeg("slepen: opstelling", false, "geen greep of te weinig blokken");
  } else {
    var gr = greep.getBoundingClientRect(), dr = doelBlok.getBoundingClientRect();
    pev("pointerdown", gr.left + 5, gr.top + 5, greep);
    pev("pointermove", gr.left + 40, gr.top + 40);
    zeg("slepen: het spookje verschijnt", document.querySelectorAll(".pdrag-ghost").length === 1);
    zeg("slepen: de bron vervaagt", eerste.classList.contains("pdrag-bron"));
    // bovenhelft van het doel -> ervóór; onderhelft -> erná. Allebei moeten ze te zien zijn.
    pev("pointermove", dr.left + 150, dr.top + 3);
    zeg("slepen: boven het doel toont 'ervoor'", doelBlok.classList.contains("over-boven"),
        "klassen: " + doelBlok.className);
    pev("pointermove", dr.left + 150, dr.bottom - 3);
    zeg("slepen: onder het doel toont 'erna'", doelBlok.classList.contains("over-onder"),
        "klassen: " + doelBlok.className);
    pev("pointerup", dr.left + 150, dr.bottom - 3);
    zeg("slepen: het blok is verplaatst", rij() !== volgordeVoor, volgordeVoor + " -> " + rij());
    zeg("slepen: het spookje is opgeruimd", document.querySelectorAll(".pdrag-ghost").length === 0);
    var rest = [].slice.call(b.querySelectorAll(".over,.over-boven,.over-onder,.pdrag-bron"));
    zeg("slepen: geen sleep-klassen achtergebleven", rest.length === 0,
        rest.length ? rest[0].className : "");
    // De greep hoort te vertellen dat je hem kunt slepen — daar ging het mis.
    var nieuweGreep = b.querySelector(".wb-greep-knop");
    zeg("de greep zegt dat je hem kunt slepen",
        !!(nieuweGreep && (nieuweGreep.getAttribute("title") || "").toLowerCase().indexOf("drag") > -1),
        nieuweGreep ? (nieuweGreep.getAttribute("title") || "(geen)") : "(geen greep)");
  }

  // 9. EEN BLOK TOEVOEGEN ZONDER MARKDOWN TE KENNEN
  //
  // De plus doet letterlijk wat typen doet (een blok met een "/" en dan het bestaande menu), dus
  // dit meet meteen of dat ene pad nog heel is. Tabel en codeblok lopen NIET langs `execCommand`:
  // die krijgen hun markdown-sjabloon van de server en openen het bron-bewerkvlak.
  var blokkenVoor = b.querySelectorAll(":scope > .wb").length;
  var gastheer = b.querySelector(":scope > .wb");
  var plusKnop = gastheer && gastheer.querySelector(".wb-plus");
  zeg("de plus staat in de goot", !!plusKnop);
  if (plusKnop) {
    plusKnop.click();
    zeg("de plus voegt een blok toe",
        b.querySelectorAll(":scope > .wb").length === blokkenVoor + 1);
    var opn = [].slice.call(b.querySelectorAll(".wb-menu")).filter(function (m) {
      return !m.hidden && !m.id;
    });
    zeg("het menu gaat vanzelf open", opn.length === 1, opn.length + " open");
    if (opn.length === 1) {
      var items = [].slice.call(opn[0].querySelectorAll("[data-wiki-cmd]"));
      var namen = items.map(function (i) { return i.textContent; });
      zeg("het menu dekt ook tabel en code",
          namen.indexOf("Tabel") > -1 && namen.indexOf("Codeblok") > -1, namen.join("/"));
      var tabel = items.filter(function (i) { return i.textContent === "Tabel"; })[0];
      if (tabel) {
        tabel.click();
        var veld = b.querySelector("textarea[data-blok-bron]");
        zeg("tabel opent het bron-bewerkvlak", !!veld);
        zeg("met het sjabloon van de server erin",
            !!veld && veld.value.indexOf("|") === 0, veld ? veld.value.split("\n")[0] : "");
        zeg("de schuine streep is opgeruimd",
            !!veld && veld.value.indexOf("/") === -1);
      }
    }
  }

  // OOK OP `window`, niet alleen in de console. `console.table` is prima voor een mens, maar
  // onleesbaar voor wie de check geautomatiseerd draait — en dan is de uitslag alleen te zien
  // door er met je ogen bij te zitten. Dat is precies hoe "geen drag-and-drop" kon ontstaan.
  window.__blokcheck = uit;
  console.table(uit);
  console.log(uit.every(function (r) { return r.uitslag === "✓"; })
    ? "ALLES GOED in " + navigator.userAgent.split(") ")[0].split("(")[1]
    : "LET OP: er staat een ✗ FOUT in de tabel hierboven");
  console.log("Herlaad de pagina; er is niets opgeslagen.");
})();
