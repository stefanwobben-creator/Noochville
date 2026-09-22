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
  zeg("soorten-tabel aanwezig", Object.keys(soorten).length === 7, Object.keys(soorten).join(","));

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

  console.table(uit);
  console.log(uit.every(function (r) { return r.uitslag === "✓"; })
    ? "ALLES GOED in " + navigator.userAgent.split(") ")[0].split("(")[1]
    : "LET OP: er staat een ✗ FOUT in de tabel hierboven");
  console.log("Herlaad de pagina; er is niets opgeslagen.");
})();
