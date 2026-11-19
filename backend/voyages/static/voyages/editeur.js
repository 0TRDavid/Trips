// Éditeur Markdown de l'admin : EasyMDE sur chaque <textarea class="editeur-markdown">.
// L'aperçu est rendu par le serveur (même moteur que le site), pas par EasyMDE.
"use strict";
(function () {
  function jetonCsrf(textarea) {
    var champ = textarea.form && textarea.form.querySelector("[name=csrfmiddlewaretoken]");
    return champ ? champ.value : "";
  }

  function bouton(name, action, icone, titre, noDisable) {
    return { name: name, action: action, icon: icone, title: titre, noDisable: !!noDisable };
  }

  function initialiser(textarea) {
    var url = textarea.dataset.apercuUrl;
    var minuteur = null;
    var dernierTexte = null;
    var dernierHtml = "";

    var editeur = new EasyMDE({
      element: textarea,
      forceSync: true, // la textarea reste à jour : le formulaire Django l'envoie normalement
      spellChecker: false, // celui d'EasyMDE est anglais ; on garde celui du navigateur
      nativeSpellcheck: true,
      inputStyle: "textarea",
      autoDownloadFontAwesome: false, // pas de CDN : icônes en texte ci-dessous
      sideBySideFullscreen: false,
      minHeight: "320px",
      status: [{
        className: "mots",
        defaultValue: function (el) { el.textContent = ""; },
        onUpdate: function (el) {
          var n = (editeur.value().match(/\S+/g) || []).length;
          el.textContent = n + (n > 1 ? " mots" : " mot");
        },
      }],
      toolbar: [
        bouton("bold", EasyMDE.toggleBold, "<b>G</b>", "Gras"),
        bouton("italic", EasyMDE.toggleItalic, "<i>I</i>", "Italique"),
        bouton("heading", EasyMDE.toggleHeadingSmaller, "T", "Intertitre"),
        "|",
        bouton("quote", EasyMDE.toggleBlockquote, "«&nbsp;»", "Citation"),
        bouton("unordered-list", EasyMDE.toggleUnorderedList, "•", "Liste"),
        bouton("ordered-list", EasyMDE.toggleOrderedList, "1.", "Liste numérotée"),
        bouton("link", EasyMDE.drawLink, "lien", "Lien"),
        bouton("horizontal-rule", EasyMDE.drawHorizontalRule, "—", "Séparateur"),
        "|",
        bouton("preview", EasyMDE.togglePreview, "aperçu", "Aperçu", true),
        bouton("side-by-side", EasyMDE.toggleSideBySide, "côte à côte", "Aperçu côte à côte", true),
        bouton("fullscreen", EasyMDE.toggleFullScreen, "plein écran", "Plein écran", true),
        "|",
        bouton("guide", function () { window.open("https://commonmark.org/help/", "_blank", "noopener"); },
          "?", "Aide Markdown"),
      ],
      previewRender: function (texte, apercu) {
        if (texte === dernierTexte) return dernierHtml;
        clearTimeout(minuteur);
        minuteur = setTimeout(function () {
          var corps = new FormData();
          corps.append("texte", texte);
          fetch(url, {
            method: "POST",
            body: corps,
            credentials: "same-origin",
            headers: { "X-CSRFToken": jetonCsrf(textarea) },
          })
            .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
            .then(function (donnees) {
              dernierTexte = texte;
              dernierHtml = donnees.html || "<p class=\"apercu-vide\">(récit vide)</p>";
              apercu.innerHTML = dernierHtml;
            })
            .catch(function (e) { apercu.innerHTML = "<p class=\"apercu-erreur\">Aperçu indisponible (" + e.message + ")</p>"; });
        }, 250);
        return dernierHtml || "<p class=\"apercu-vide\">…</p>";
      },
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("textarea.editeur-markdown").forEach(initialiser);
  });
})();
