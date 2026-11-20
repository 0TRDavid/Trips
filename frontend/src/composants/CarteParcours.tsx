import { useEffect, useRef } from "react";
import { Map as MapLibre, NavigationControl, setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// MapLibre cherche son worker à côté de son propre fichier, ce qui échoue
// quand Vite le regroupe (node_modules/.vite/deps). On lui donne l'URL que
// Vite sert (dev) ou copie dans le build. Ce worker n'importe rien d'autre.
import urlWorker from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { PointTrace } from "../api/types";
import { bornes, cadrageJour, ligneTrace, pointsTrace } from "../lib/carte";
import styles from "./CarteParcours.module.css";

/**
 * Tuiles vectorielles OpenFreeMap : gratuites, sans clé ni compte.
 * Style « liberty », en couleur ; à la v2, on le remplacera par un style
 * maison (Maputnik) sur les mêmes tuiles. Voir docs/decisions.md.
 */
const STYLE = "https://tiles.openfreemap.org/styles/liberty";

setWorkerUrl(urlWorker);

type Props = {
  trace: PointTrace[];
  /** Jour sélectionné (AAAA-MM-JJ) ou null pour tout le voyage. */
  selection: string | null;
  surSelection: (jour: string) => void;
};

const mouvementReduit = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const tactile = () => window.matchMedia("(pointer: coarse)").matches;

function couleur(nom: string, repli: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nom).trim() || repli;
}

/**
 * Carte du parcours (MapLibre GL).
 *
 * React ne gère pas l'intérieur de la carte : MapLibre dessine dans un
 * <canvas> qu'il pilote lui-même. On crée donc la carte une seule fois
 * (useEffect), on garde l'objet dans une ref, et on lui transmet ensuite
 * les changements (jour sélectionné) par ses propres méthodes.
 */
export default function CarteParcours({ trace, selection, surSelection }: Props) {
  const conteneur = useRef<HTMLDivElement>(null);
  const carte = useRef<MapLibre | null>(null);
  const chargee = useRef(false);
  // Toujours la dernière version du callback, sans recréer la carte.
  const surSelectionRef = useRef(surSelection);
  surSelectionRef.current = surSelection;
  const selectionRef = useRef(selection);
  selectionRef.current = selection;

  // Création de la carte (une fois par tracé).
  useEffect(() => {
    if (!conteneur.current) return;
    const b = bornes(trace);
    const accent = couleur("--accent", "#b4532a");
    const encre = couleur("--encre", "#1d1b18");

    const map = new MapLibre({
      container: conteneur.current,
      style: STYLE,
      bounds: b ?? undefined,
      center: b ? undefined : [139.7, 35.7],
      zoom: b ? undefined : 4,
      fitBoundsOptions: { padding: 48 },
      attributionControl: { compact: true },
      // Sur téléphone, un doigt fait défiler la page, deux doigts bougent la carte.
      cooperativeGestures: tactile(),
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
    });
    map.touchZoomRotate.disableRotation();
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    carte.current = map;

    map.on("load", () => {
      map.addSource("ligne", { type: "geojson", data: ligneTrace(trace) });
      map.addSource("points", { type: "geojson", data: pointsTrace(trace) });
      map.addLayer({
        id: "ligne",
        type: "line",
        source: "ligne",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": encre, "line-width": 1.5, "line-opacity": 0.55, "line-dasharray": [2, 2] },
      });
      map.addLayer({
        id: "points",
        type: "circle",
        source: "points",
        paint: {
          "circle-radius": 5,
          "circle-color": encre,
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 1.5,
        },
      });
      map.addLayer({
        id: "points-actifs",
        type: "circle",
        source: "points",
        filter: ["==", ["get", "jour"], selectionRef.current ?? ""],
        paint: {
          "circle-radius": 8,
          "circle-color": accent,
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 2,
        },
      });
      // Zone de clic plus large que le point visible (confort au doigt).
      map.addLayer({
        id: "points-clic",
        type: "circle",
        source: "points",
        paint: { "circle-radius": 16, "circle-opacity": 0 },
      });
      map.on("click", "points-clic", (e) => {
        const jour = e.features?.[0]?.properties?.jour;
        if (typeof jour === "string") surSelectionRef.current(jour);
      });
      map.on("mouseenter", "points-clic", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "points-clic", () => (map.getCanvas().style.cursor = ""));
      chargee.current = true;
      cadrer(map, trace, selectionRef.current, true);
    });

    return () => {
      chargee.current = false;
      carte.current = null;
      map.remove();
    };
  }, [trace]);

  // Changement de jour sélectionné : mise en évidence + zoom.
  useEffect(() => {
    const map = carte.current;
    if (!map || !chargee.current) return;
    map.setFilter("points-actifs", ["==", ["get", "jour"], selection ?? ""]);
    cadrer(map, trace, selection, false);
  }, [selection, trace]);

  return (
    <div
      ref={conteneur}
      className={styles.carte}
      role="region"
      aria-label="Carte du parcours"
    />
  );
}

/** Zoome sur un jour (ses photos géolocalisées) ou sur tout le voyage. */
function cadrer(map: MapLibre, trace: PointTrace[], jour: string | null, instantane: boolean) {
  const duration = instantane || mouvementReduit() ? 0 : 900;
  const padding = { top: 56, bottom: 56, left: 56, right: 56 };
  if (jour) {
    const c = cadrageJour(trace, jour);
    if (c.type === "point") {
      map.flyTo({ center: [c.lon, c.lat], zoom: 14, duration });
      return;
    }
    if (c.type === "bornes") {
      map.fitBounds(c.bornes, { padding, maxZoom: 15, duration });
      return;
    }
    // Jour sans position : la carte ne bouge pas.
    return;
  }
  const b = bornes(trace);
  if (b) map.fitBounds(b, { padding, maxZoom: 12, duration });
}
