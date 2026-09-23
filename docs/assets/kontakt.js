// Setzt die E-Mail-Adresse erst im Browser zusammen. Im HTML-Quelltext steht sie nur
// rückwärts und zerlegt, damit einfache Adress-Sammler sie nicht per Mustersuche finden.
(function () {
  "use strict";
  function umdrehen(s) { return s.split("").reverse().join(""); }
  document.querySelectorAll(".kontakt-mail[data-u][data-d]").forEach(function (el) {
    var adresse = umdrehen(el.dataset.u) + "@" + umdrehen(el.dataset.d);
    var a = document.createElement("a");
    a.href = "mai" + "lto:" + adresse;
    a.textContent = adresse;
    el.textContent = "";
    el.appendChild(a);
  });
})();
