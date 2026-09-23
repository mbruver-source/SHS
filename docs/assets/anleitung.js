// Rendert HANDBUCH.md bzw. UMSTIEG.md im Browser, damit die Markdown-Dateien die einzige
// Quelle bleiben. Welche Datei geladen wird, steht fest im data-quelle-Attribut der Seite
// (keine URL-Parameter -> es kann keine beliebige Datei nachgeladen werden).
(function () {
  "use strict";

  var REPO = "https://github.com/mbruver-source/SHS/blob/main/";
  // Querverweise zwischen den .md-Dateien auf die jeweilige Website-Seite umbiegen
  var SEITEN = { "HANDBUCH.md": "handbuch.html", "UMSTIEG.md": "umstieg.html" };

  var main = document.querySelector("main[data-quelle]");
  var doku = main.querySelector(".doku");
  var navi = main.querySelector(".inhalt-navi ol");
  var naviMobil = main.querySelector(".inhalt-navi-mobil ol");

  // Anker wie GitHub: klein, Satzzeichen weg (Umlaute bleiben), jedes Leerzeichen -> "-"
  function slug(text, vergeben) {
    var basis = text.trim().toLowerCase()
      .replace(/[^\p{L}\p{N}\s_-]/gu, "")
      .replace(/\s/g, "-");
    var s = basis, n = 1;
    while (vergeben[s]) { s = basis + "-" + n++; }
    vergeben[s] = true;
    return s;
  }

  function linkUmschreiben(a) {
    var href = a.getAttribute("href") || "";
    if (/^(https?:|mailto:|#)/i.test(href)) { return; }
    var teile = href.split("#");
    var pfad = teile[0], anker = teile[1] ? "#" + teile[1] : "";
    if (SEITEN[pfad]) {
      a.setAttribute("href", SEITEN[pfad] + anker);
    } else if (pfad.indexOf("../") === 0) {
      // Dateien außerhalb von docs/ (z. B. README_CONTAINER.md) liegen nur im Repo
      a.setAttribute("href", REPO + pfad.slice(3) + anker);
    }
  }

  function inhaltsverzeichnis(ueberschriften) {
    ueberschriften.forEach(function (h) {
      [navi, naviMobil].forEach(function (liste) {
        var li = document.createElement("li");
        var a = document.createElement("a");
        a.href = "#" + h.id;
        a.textContent = h.textContent;
        li.appendChild(a);
        liste.appendChild(li);
      });
    });

    if (!("IntersectionObserver" in window)) { return; }
    var links = navi.querySelectorAll("a");
    var beobachter = new IntersectionObserver(function (eintraege) {
      eintraege.forEach(function (e) {
        if (!e.isIntersecting) { return; }
        links.forEach(function (a) {
          a.classList.toggle("aktiv", a.getAttribute("href") === "#" + e.target.id);
        });
      });
    }, { rootMargin: "-10% 0px -75% 0px" });
    ueberschriften.forEach(function (h) { beobachter.observe(h); });
  }

  // Der Inhalt entsteht erst nach dem Laden - die automatische Scroll-Wiederherstellung
  // des Browsers würde den Sprung zum Anker sonst überschreiben
  if (location.hash && "scrollRestoration" in history) { history.scrollRestoration = "manual"; }

  fetch(main.dataset.quelle, { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.text();
    })
    .then(function (md) {
      // Inhalt stammt aus dem eigenen Repository, nicht von Nutzern
      doku.innerHTML = marked.parse(md, { gfm: true });

      var vergeben = {};
      doku.querySelectorAll("h1, h2, h3, h4").forEach(function (h) { h.id = slug(h.textContent, vergeben); });
      doku.querySelectorAll("a[href]").forEach(linkUmschreiben);
      doku.querySelectorAll("table").forEach(function (t) {
        var huelle = document.createElement("div");
        huelle.className = "tabelle-huelle";
        t.parentNode.insertBefore(huelle, t);
        huelle.appendChild(t);
      });

      // Das eigene "Inhalt"-Kapitel des Handbuchs ersetzt die Seitenleiste
      var h2s = Array.prototype.slice.call(doku.querySelectorAll("h2"));
      var inhalt = h2s.filter(function (h) { return h.textContent.trim() === "Inhalt"; })[0];
      if (inhalt) {
        var naechstes = inhalt.nextElementSibling;
        if (naechstes && naechstes.tagName === "OL") { naechstes.remove(); }
        inhalt.remove();
        h2s.splice(h2s.indexOf(inhalt), 1);
      }
      inhaltsverzeichnis(h2s);

      var h1 = doku.querySelector("h1");
      if (h1) {
        var t = h1.textContent.trim();
        document.title = t.indexOf("SHS-Prüfungsprogramm") >= 0 ? t : t + " · SHS-Prüfungsprogramm";
      }

      // Nach dem Rendern zum Anker aus der Adresse springen - und nochmals, sobald die
      // Bilder darüber geladen sind, weil sie das Ziel sonst nach unten verschieben
      if (location.hash) {
        // Ein kaputter Anker (z. B. "#%E0") darf nur den Sprung verhindern, nicht die Anzeige
        var ziel = null;
        try { ziel = document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch (e) { /* ignorieren */ }
        if (ziel) {
          ziel.scrollIntoView({ behavior: "instant" });
          var offen = Array.prototype.filter.call(doku.querySelectorAll("img"), function (img) {
            return !img.complete && (ziel.compareDocumentPosition(img) & Node.DOCUMENT_POSITION_PRECEDING);
          });
          Promise.all(offen.map(function (img) {
            return new Promise(function (fertig) { img.addEventListener("load", fertig); img.addEventListener("error", fertig); });
          })).then(function () { ziel.scrollIntoView({ behavior: "instant" }); });
        }
      }
    })
    .catch(function (err) {
      doku.innerHTML = "";
      var p = document.createElement("p");
      p.className = "fehler";
      p.textContent = "Die Anleitung konnte nicht geladen werden (" + err.message + "). ";
      var a = document.createElement("a");
      a.href = REPO + "docs/" + main.dataset.quelle;
      a.textContent = "Direkt auf GitHub lesen";
      p.appendChild(a);
      doku.appendChild(p);
    });
})();
