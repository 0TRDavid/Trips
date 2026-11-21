// Écran « Compléter les médias » (admin) : date et position des médias qui n'en
// ont pas. JS sans framework ; les données viennent de admin_completion.py, les
// écritures passent par POST /completer/appliquer/ (logique dans completion.py).
//
// Tout le texte venant des données est posé avec textContent (jamais innerHTML).

const racine = document.getElementById("completer");
const config = JSON.parse(document.getElementById("config-completer").textContent);
const $ = (id) => document.getElementById(id);
const mouvementReduit = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const STYLE_CARTE = "https://tiles.openfreemap.org/styles/liberty"; // même style que le site
const ACCENT = "#b4532a";

const FILTRES = [
  ["a_completer", "À compléter"],
  ["sans_date", "Sans date"],
  ["a_confirmer", "Date à confirmer"],
  ["sans_position", "Sans position"],
  ["tout", "Tout"],
];
const SOURCES_DATE = {
  "": "date du fichier, provisoire",
  exif: "métadonnées",
  nom_fichier: "nom du fichier",
  manuel: "saisie à la main",
};
const SOURCES_POSITION = { "": "sans position", exif: "GPS du fichier", manuel: "placée à la main" };

const etat = {
  voyage: config.voyage,
  contexte: null,
  filtre: "a_completer",
  medias: [],
  selection: new Set(),
  focus: null, // id du média affiché dans l'aperçu
  ancre: null, // début d'une sélection par plage (Maj+clic)
  jour: null, // date affichée dans la bande
  bande: [],
  reference: null, // média de la bande pris comme référence
};

// --- Utilitaires -------------------------------------------------------------------

function el(balise, attributs = {}, ...enfants) {
  const noeud = document.createElement(balise);
  for (const [cle, valeur] of Object.entries(attributs)) {
    if (valeur === null || valeur === undefined || valeur === false) continue;
    if (cle === "class") noeud.className = valeur;
    else if (cle === "style") Object.assign(noeud.style, valeur);
    else if (cle.startsWith("on")) noeud.addEventListener(cle.slice(2), valeur);
    else noeud.setAttribute(cle, valeur === true ? "" : valeur);
  }
  for (const enfant of enfants.flat()) {
    if (enfant === null || enfant === undefined || enfant === false) continue;
    noeud.append(enfant instanceof Node ? enfant : document.createTextNode(String(enfant)));
  }
  return noeud;
}

async function lire(url, params) {
  const reponse = await fetch(`${url}?${new URLSearchParams(params)}`, { credentials: "same-origin" });
  const donnees = await reponse.json().catch(() => ({}));
  if (!reponse.ok) throw new Error(donnees.erreur || `Erreur ${reponse.status}`);
  return donnees;
}

async function appliquer(action, extra = {}) {
  const ids = [...etat.selection];
  if (!ids.length) {
    message("Sélectionner d'abord un ou plusieurs médias.", "erreur");
    return null;
  }
  const reponse = await fetch(config.urls.appliquer, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": racine.dataset.csrf },
    body: JSON.stringify({ voyage: etat.voyage, ids, action, ...extra }),
  });
  const donnees = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    message(donnees.erreur || `Erreur ${reponse.status}`, "erreur");
    return null;
  }
  return donnees.medias;
}

let minuterieMessage;
function message(texte, type = "succes") {
  const zone = $("cm-message");
  zone.textContent = texte;
  zone.dataset.type = type;
  clearTimeout(minuterieMessage);
  minuterieMessage = setTimeout(() => (zone.textContent = ""), 6000);
}

// « 3 médias », « 2 autres médias » : chaque mot s'accorde.
const pluriel = (n, mots) => `${n} ${mots.split(" ").map((mot) => mot + (n > 1 ? "s" : "")).join(" ")}`;
const dateLocale = (instant) => instant.slice(0, 10);
const heureLocale = (instant) => instant.slice(11, 19);
const ms = (instant) => new Date(instant).getTime();

function dateLisible(iso) {
  const [a, m, j] = iso.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, j)).toLocaleDateString("fr-FR", {
    weekday: "short", day: "numeric", month: "short", timeZone: "UTC",
  });
}

const parId = (id) => etat.medias.find((m) => m.id === id) || etat.bande.find((m) => m.id === id);
const selectionnes = () => etat.medias.filter((m) => etat.selection.has(m.id));
const aPosition = (m) => m.lat !== null && m.lon !== null;
// Un média sert de repère (bande, référence) si sa date est fiable.
const dateFiable = (m) => m.source_date !== "" && !m.date_a_confirmer;
const reperes = () => etat.bande.filter((m) => dateFiable(m) && !etat.selection.has(m.id));

function vignette(media, classe = "cm-vignette") {
  return el("span", { class: classe, style: { background: media.couleur, aspectRatio: String(media.ratio) } },
    media.miniature ? el("img", { src: media.miniature, alt: "", loading: "lazy" }) : null,
    media.type !== "photo" ? el("span", { class: "cm-type" }, media.type === "video" ? "▶" : "◉") : null,
  );
}

function badges(media) {
  return el("span", { class: "cm-badges" },
    media.source_date === "" ? el("span", { class: "cm-badge cm-badge--alerte" }, "sans date") : null,
    media.date_a_confirmer ? el("span", { class: "cm-badge cm-badge--alerte" }, "à confirmer") : null,
    !aPosition(media) ? el("span", { class: "cm-badge" }, "sans position") : null,
    !media.visible ? el("span", { class: "cm-badge cm-badge--discret" }, "masqué") : null,
  );
}

// --- Chargements -------------------------------------------------------------------

async function chargerVoyage() {
  etat.contexte = await lire(config.urls.voyage, { voyage: etat.voyage });
  rendreChoixJour();
  majCarteFond(true);
}

async function chargerMedias() {
  const donnees = await lire(config.urls.medias, { voyage: etat.voyage, filtre: etat.filtre });
  etat.medias = donnees.medias;
  const presents = new Set(etat.medias.map((m) => m.id));
  etat.selection = new Set([...etat.selection].filter((id) => presents.has(id)));
  if (!presents.has(etat.focus)) etat.focus = [...etat.selection][0] ?? null;
  rendreFiltres(donnees.comptes);
  rendreListe();
}

async function chargerJour(date) {
  etat.jour = date;
  $("cm-jour").value = date || "";
  etat.bande = date ? (await lire(config.urls.jour, { voyage: etat.voyage, date })).medias : [];
  choisirReferenceParDefaut();
  rendreBande();
  cadrerJour();
}

async function toutRecharger() {
  await Promise.all([chargerVoyage(), chargerMedias()]);
  await chargerJour(etat.jour);
  rendreSelection();
}

// --- Barre et liste ----------------------------------------------------------------

function rendreChoixVoyage() {
  const choix = $("cm-voyage");
  choix.replaceChildren(...config.voyages.map((v) =>
    el("option", { value: v.id, selected: v.id === etat.voyage }, `${v.titre} (${v.a_completer} à compléter)`)));
}

function rendreFiltres(comptes) {
  $("cm-filtres").replaceChildren(...FILTRES.map(([cle, libelle]) =>
    el("button", {
      type: "button", class: "cm-filtre", "aria-pressed": String(cle === etat.filtre),
      onclick: async () => { etat.filtre = cle; await chargerMedias(); rendreSelection(); },
    }, libelle, el("span", { class: "cm-nb" }, comptes[cle]))));
}

function rendreListe() {
  const liste = $("cm-medias");
  if (!etat.medias.length) {
    liste.replaceChildren(el("li", { class: "cm-vide" }, "Rien à compléter ici. 🎉"));
    return;
  }
  let jourCourant = null;
  const elements = [];
  for (const media of etat.medias) {
    if (media.jour !== jourCourant) {
      jourCourant = media.jour;
      elements.push(el("li", { class: "cm-intertitre" }, dateLisible(media.jour)));
    }
    elements.push(el("li", {},
      el("button", {
        type: "button", class: "cm-media", "data-id": media.id, title: media.nom,
        onclick: (e) => cliquerMedia(media.id, e),
      },
        vignette(media),
        el("span", { class: "cm-media-texte" },
          el("span", { class: "cm-media-nom" }, media.nom),
          el("span", { class: "cm-media-heure" }, heureLocale(media.instant).slice(0, 5),
            media.photographe ? ` · ${media.photographe}` : ""),
          badges(media)),
      )));
  }
  liste.replaceChildren(...elements);
  rendreEtatListe();
}

function rendreEtatListe() {
  for (const bouton of $("cm-medias").querySelectorAll(".cm-media")) {
    const id = Number(bouton.dataset.id);
    bouton.setAttribute("aria-pressed", String(etat.selection.has(id)));
    bouton.classList.toggle("cm-media--focus", id === etat.focus);
  }
  const n = etat.selection.size;
  $("cm-selection").textContent = n ? `${pluriel(n, "média")} sélectionné${n > 1 ? "s" : ""}` : "Aucune sélection";
}

async function cliquerMedia(id, evenement) {
  const ids = etat.medias.map((m) => m.id);
  if (evenement.shiftKey && etat.ancre !== null) {
    const [a, b] = [ids.indexOf(etat.ancre), ids.indexOf(id)].sort((x, y) => x - y);
    ids.slice(a, b + 1).forEach((i) => etat.selection.add(i));
  } else if (evenement.ctrlKey || evenement.metaKey) {
    if (etat.selection.has(id)) etat.selection.delete(id);
    else etat.selection.add(id);
    etat.ancre = id;
  } else {
    etat.selection = new Set([id]);
    etat.ancre = id;
  }
  const ancienJour = etat.focus !== null ? parId(etat.focus)?.jour : null;
  etat.focus = etat.selection.has(id) ? id : ([...etat.selection][0] ?? null);
  const media = parId(etat.focus);
  if (media && media.jour !== ancienJour) await chargerJour(media.jour);
  rendreSelection();
}

// --- Aperçu, date, bande -----------------------------------------------------------

function rendreSelection() {
  rendreEtatListe();
  rendreApercu();
  remplirDate();
  choisirReferenceParDefaut();
  rendreBande();
  majCarteSelection();
}

function rendreApercu() {
  const zone = $("cm-apercu");
  const media = parId(etat.focus);
  if (!media) {
    zone.replaceChildren(el("p", { class: "cm-aide" }, "Choisir un média dans la liste."));
    return;
  }
  const autres = selectionnes().filter((m) => m.id !== media.id);
  zone.replaceChildren(
    el("div", { class: "cm-apercu-image", style: { background: media.couleur, aspectRatio: String(media.ratio) } },
      media.image ? el("img", { src: media.image, alt: media.nom }) : null),
    el("div", { class: "cm-apercu-texte" },
      el("strong", {}, media.nom),
      el("span", {}, [media.photographe, media.type === "photo" ? null : media.type === "video" ? "vidéo" : "photo animée"]
        .filter(Boolean).join(" · ")),
      el("span", {}, `${dateLisible(dateLocale(media.instant))} · ${heureLocale(media.instant)}`,
        el("small", {}, ` (${SOURCES_DATE[media.source_date]}${media.date_a_confirmer ? ", à confirmer" : ""})`)),
      el("span", {}, SOURCES_POSITION[media.source_position] ?? "",
        aPosition(media) ? el("small", {}, ` ${media.lat.toFixed(5)}, ${media.lon.toFixed(5)}`) : null),
      el("a", { href: config.urls.media.replace("/0/", `/${media.id}/`), target: "_blank", rel: "noopener" },
        "Fiche du média ↗"),
      autres.length ? el("span", { class: "cm-lot" }, `+ ${pluriel(autres.length, "autre média")} dans le lot`,
        el("span", { class: "cm-lot-vignettes" }, autres.slice(0, 8).map((m) => vignette(m, "cm-vignette cm-vignette--mini")))) : null,
    ),
  );
}

function remplirDate() {
  const media = parId(etat.focus);
  $("cm-date-jour").value = media ? dateLocale(media.instant) : "";
  $("cm-date-heure").value = media ? heureLocale(media.instant) : "";
  $("cm-confirmer").hidden = !selectionnes().some((m) => m.date_a_confirmer || m.source_date === "");
}

function rendreChoixJour() {
  const jours = etat.contexte?.jours ?? [];
  $("cm-jour").replaceChildren(
    el("option", { value: "" }, "—"),
    ...jours.map((j) => el("option", { value: j.date },
      `${dateLisible(j.date)} · ${pluriel(j.nb, "média")}${j.nb_visibles < j.nb ? ` (${j.nb - j.nb_visibles} masqués)` : ""}`)));
  $("cm-jour").value = etat.jour || "";
}

/** Voisine par défaut : la plus proche dans le temps qui a une position, si
 * l'heure du média choisi est fiable (métadonnées ou saisie) et dans ce jour. */
function choisirReferenceParDefaut() {
  const media = parId(etat.focus);
  const candidates = reperes();
  if (etat.reference && candidates.some((m) => m.id === etat.reference.id)) return;
  etat.reference = null;
  if (!media || media.jour !== etat.jour || !["exif", "manuel"].includes(media.source_date)) return;
  const placees = candidates.filter(aPosition);
  if (!placees.length) return;
  const t = ms(media.instant);
  etat.reference = placees.reduce((a, b) => (Math.abs(ms(a.instant) - t) <= Math.abs(ms(b.instant) - t) ? a : b));
}

function rendreBande() {
  const bande = $("cm-bande");
  const autres = reperes();
  const aDater = etat.bande.filter((m) => !dateFiable(m) && !etat.selection.has(m.id)).length;
  $("cm-bande-note").textContent = aDater
    ? `${pluriel(aDater, "autre média")} à dater ce jour-là, non affiché${aDater > 1 ? "s" : ""} : leur heure n'est pas fiable.`
    : "";
  if (!etat.jour) {
    bande.replaceChildren(el("li", { class: "cm-aide" }, "Choisir un jour."));
  } else if (!autres.length) {
    bande.replaceChildren(el("li", { class: "cm-aide" }, "Aucun autre média ce jour-là : saisir l'heure ci-dessus."));
  } else {
    const elements = [];
    autres.forEach((media, i) => {
      if (i > 0) {
        const precedent = autres[i - 1];
        elements.push(el("li", { class: "cm-fente-zone" },
          el("button", {
            type: "button", class: "cm-fente",
            title: `Placer la sélection entre ${heureLocale(precedent.instant)} et ${heureLocale(media.instant)}`,
            "aria-label": `Placer entre ${precedent.nom} et ${media.nom}`,
            onclick: () => placerEntre(precedent, media),
          }, "+")));
      }
      elements.push(el("li", {},
        el("button", {
          type: "button", class: "cm-bande-media", title: media.nom,
          "aria-pressed": String(etat.reference?.id === media.id),
          onclick: () => { etat.reference = etat.reference?.id === media.id ? null : media; rendreBande(); majCarteSelection(); },
        },
          vignette(media, "cm-vignette cm-vignette--bande"),
          el("span", { class: "cm-bande-heure" }, heureLocale(media.instant).slice(0, 5),
            aPosition(media) ? " 📍" : "", !media.visible ? " · masqué" : ""))));
    });
    bande.replaceChildren(...elements);
    bande.querySelector('[aria-pressed="true"]')?.scrollIntoView({ block: "nearest", inline: "center" });
  }
  rendreReference();
}

function rendreReference() {
  const ref = etat.reference;
  $("cm-reference").hidden = !ref;
  if (!ref) return;
  $("cm-reference-texte").textContent =
    `Référence : ${ref.nom}, ${heureLocale(ref.instant)}${aPosition(ref) ? "" : " (sans position)"}`;
  racine.querySelector('[data-reprendre="position"]').disabled = !aPosition(ref);
  racine.querySelector('[data-reprendre="tout"]').disabled = !aPosition(ref);
}

// --- Actions -----------------------------------------------------------------------

async function apresAction(medias, texte) {
  if (!medias) return;
  message(texte);
  // La bande suit le média choisi là où il a atterri.
  const focus = medias.find((m) => m.id === etat.focus) ?? medias[0];
  if (focus) etat.jour = focus.jour;
  const ancienIndex = etat.medias.findIndex((m) => m.id === etat.focus);
  etat.reference = null;
  await toutRecharger();
  if (!etat.selection.size && etat.medias.length) {
    // Le lot est complet et sort de la liste : on passe au suivant.
    const suivant = etat.medias[Math.min(Math.max(ancienIndex, 0), etat.medias.length - 1)];
    etat.selection = new Set([suivant.id]);
    etat.focus = etat.ancre = suivant.id;
    await chargerJour(suivant.jour);
    rendreSelection();
  }
}

async function placerEntre(a, b) {
  const n = etat.selection.size;
  const medias = await appliquer("entre", { a: a.id, b: b.id });
  await apresAction(medias, `${pluriel(n, "média")} placé${n > 1 ? "s" : ""} entre ${heureLocale(a.instant)} et ${heureLocale(b.instant)}.`);
}

$("cm-date").addEventListener("submit", async (e) => {
  e.preventDefault();
  const jour = $("cm-date-jour").value;
  let heure = $("cm-date-heure").value;
  if (!jour || !heure) return;
  if (heure.length === 5) heure += ":00";
  const n = etat.selection.size;
  const medias = await appliquer("date", { instant: `${jour}T${heure}` });
  await apresAction(medias, `Date appliquée à ${pluriel(n, "média")}.`);
});

$("cm-confirmer").addEventListener("click", async () => {
  const n = etat.selection.size;
  const medias = await appliquer("confirmer");
  await apresAction(medias, `Date confirmée pour ${pluriel(n, "média")}.`);
});

for (const bouton of racine.querySelectorAll("[data-reprendre]")) {
  bouton.addEventListener("click", async () => {
    if (!etat.reference) return;
    const quoi = bouton.dataset.reprendre;
    const position = quoi !== "heure";
    const heure = quoi !== "position";
    const n = etat.selection.size;
    const medias = await appliquer("reprendre", { reference: etat.reference.id, position, heure });
    const repris = position && heure ? "position et heure reprises" : position ? "position reprise" : "heure reprise";
    await apresAction(medias, `${pluriel(n, "média")} : ${repris} de ${etat.reference.nom}.`);
  });
}

async function placerIci(lat, lon) {
  const n = etat.selection.size;
  const medias = await appliquer("position", { lat, lon });
  fermerCandidat();
  await apresAction(medias, `${pluriel(n, "média")} placé${n > 1 ? "s" : ""} sur la carte.`);
}

$("cm-tout").addEventListener("click", () => {
  etat.selection = new Set(etat.medias.map((m) => m.id));
  if (etat.focus === null && etat.medias.length) etat.focus = etat.medias[0].id;
  rendreSelection();
});
$("cm-aucun").addEventListener("click", () => {
  etat.selection.clear();
  etat.focus = null;
  rendreSelection();
});
$("cm-jour").addEventListener("change", async (e) => {
  etat.reference = null;
  await chargerJour(e.target.value || null);
  majCarteSelection();
});
$("cm-voyage").addEventListener("change", async (e) => {
  etat.voyage = Number(e.target.value);
  etat.selection.clear();
  etat.focus = etat.ancre = etat.jour = etat.reference = null;
  history.replaceState(null, "", `?voyage=${etat.voyage}`);
  await toutRecharger();
});

// --- Recherche de lieu -------------------------------------------------------------

$("cm-recherche").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = $("cm-lieu").value.trim();
  const liste = $("cm-resultats");
  if (q.length < 2) return;
  liste.hidden = false;
  liste.replaceChildren(el("li", { class: "cm-aide" }, "Recherche…"));
  try {
    const { resultats } = await lire(config.urls.lieux, { voyage: etat.voyage, q });
    liste.replaceChildren(...(resultats.length ? resultats.map((r) =>
      el("li", {}, el("button", {
        type: "button",
        onclick: () => { liste.hidden = true; montrerCandidat(r.lat, r.lon, r.nom, 15); },
      }, r.nom))) : [el("li", { class: "cm-aide" }, "Aucun lieu trouvé.")]));
  } catch (erreur) {
    liste.replaceChildren(el("li", { class: "cm-aide" }, erreur.message));
  }
});

// --- Carte -------------------------------------------------------------------------

let carte = null;
let maplibre = null;
let popupCandidat = null;
let carteChargee = false;

const vide = () => ({ type: "FeatureCollection", features: [] });
const point = (lon, lat, proprietes = {}) =>
  ({ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: proprietes });

async function creerCarte() {
  maplibre = await import(racine.dataset.maplibre);
  maplibre.setWorkerUrl(racine.dataset.worker);
  carte = new maplibre.Map({
    container: "cm-carte",
    style: STYLE_CARTE,
    center: [139.7, 35.68],
    zoom: 4,
    attributionControl: { compact: true },
  });
  carte.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
  carte.on("load", () => {
    carte.addSource("trace", { type: "geojson", data: vide() });
    carte.addSource("positions", { type: "geojson", data: vide() });
    carte.addSource("selection", { type: "geojson", data: vide() });
    carte.addSource("reference", { type: "geojson", data: vide() });
    carte.addLayer({ id: "trace", type: "line", source: "trace",
      paint: { "line-color": ACCENT, "line-width": 2, "line-opacity": 0.45 } });
    carte.addLayer({ id: "positions", type: "circle", source: "positions",
      paint: { "circle-radius": 3.5, "circle-color": "#555", "circle-opacity": 0.55,
               "circle-stroke-color": "#fff", "circle-stroke-width": 1 } });
    carte.addLayer({ id: "reference", type: "circle", source: "reference",
      paint: { "circle-radius": 10, "circle-color": "transparent",
               "circle-stroke-color": "#1f6feb", "circle-stroke-width": 3 } });
    carte.addLayer({ id: "selection", type: "circle", source: "selection",
      paint: { "circle-radius": 7, "circle-color": ACCENT, "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
    carteChargee = true;
    majCarteFond(true);
    cadrerJour();
    majCarteSelection();
  });
  carte.on("click", (e) => montrerCandidat(e.lngLat.lat, e.lngLat.lng, null));
}

function bouger(options) {
  if (mouvementReduit()) carte.jumpTo(options);
  else carte.easeTo({ ...options, duration: 600 });
}

function majCarteFond(cadrer = false) {
  if (!carteChargee || !etat.contexte) return;
  const { trace, positions, zone } = etat.contexte;
  carte.getSource("trace").setData({
    type: "Feature", properties: {},
    geometry: { type: "LineString", coordinates: trace.map((p) => [p.lon, p.lat]) },
  });
  carte.getSource("positions").setData({
    type: "FeatureCollection", features: positions.map((p) => point(p.lon, p.lat, { id: p.id })),
  });
  if (cadrer && zone) {
    carte.fitBounds([[zone[0], zone[1]], [zone[2], zone[3]]], { padding: 40, animate: false, maxZoom: 14 });
  }
}

/** Cadre la carte sur les positions connues du jour affiché dans la bande. */
function cadrerJour() {
  if (!carteChargee || !etat.contexte || !etat.jour) return;
  const points = etat.contexte.positions.filter((p) => p.jour === etat.jour);
  if (!points.length) return;
  const lons = points.map((p) => p.lon);
  const lats = points.map((p) => p.lat);
  carte.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
    { padding: 50, maxZoom: 15, animate: !mouvementReduit(), duration: 600 });
}

function majCarteSelection() {
  if (!carteChargee) return;
  const places = selectionnes().filter(aPosition);
  carte.getSource("selection").setData({
    type: "FeatureCollection", features: places.map((m) => point(m.lon, m.lat)),
  });
  const ref = etat.reference;
  carte.getSource("reference").setData(ref && aPosition(ref)
    ? { type: "FeatureCollection", features: [point(ref.lon, ref.lat)] } : vide());
  // Le média choisi a déjà une position : on la montre (sinon, la carte reste
  // cadrée sur le jour).
  const focus = parId(etat.focus);
  if (focus && aPosition(focus)) bouger({ center: [focus.lon, focus.lat] });
}

function fermerCandidat() {
  popupCandidat?.remove();
  popupCandidat = null;
}

function montrerCandidat(lat, lon, nom, zoom) {
  if (!carte) return;
  fermerCandidat();
  const n = etat.selection.size;
  const contenu = el("div", { class: "cm-popup" },
    nom ? el("p", {}, nom) : null,
    el("p", { class: "cm-aide" }, `${lat.toFixed(5)}, ${lon.toFixed(5)}`),
    n ? el("button", { type: "button", class: "button default", onclick: () => placerIci(lat, lon) },
      `Placer ${pluriel(n, "média")} ici`) : el("p", {}, "Sélectionner d'abord des médias."));
  popupCandidat = new maplibre.Popup({ closeOnClick: false, maxWidth: "280px" })
    .setLngLat([lon, lat]).setDOMContent(contenu).addTo(carte);
  if (zoom) bouger({ center: [lon, lat], zoom });
}

// --- Démarrage ---------------------------------------------------------------------

rendreChoixVoyage();
if (etat.voyage !== null) {
  creerCarte().catch((erreur) => message(`Carte indisponible : ${erreur.message}`, "erreur"));
  toutRecharger().catch((erreur) => message(erreur.message, "erreur"));
} else {
  message("Aucun voyage importé.", "erreur");
}
