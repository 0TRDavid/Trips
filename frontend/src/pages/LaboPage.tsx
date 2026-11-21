import { useEffect, useRef, useState } from "react";
import { useJour, useVoyage, useVoyages } from "../api/requetes";
import { useTitre } from "../hooks/useTitre";
import { chemins } from "../lib/chemins";
import type { Reglages } from "../lib/mouvement";
import { REGLAGES_DEFAUT, enregistrerReglages, reglages } from "../lib/mouvement";
import { idPhoto, idVoyage } from "../lib/transitions";
import styles from "./LaboPage.module.css";

/**
 * Labo des transitions (dev uniquement, /labo).
 *
 * Le labo ne contient aucune démo recopiée : il affiche le VRAI site dans
 * deux iframes (téléphone et ordinateur) et le pilote (window.__carnet,
 * main.tsx). Les réglages (ralenti, mouvement réduit) passent par
 * localStorage : les iframes, de même origine, les reçoivent par l'événement
 * `storage` et les appliquent dès la transition suivante (lib/mouvement.ts).
 */

type Pilote = {
  naviguer: (vers: string, options?: { replace?: boolean; state?: unknown; preventScrollReset?: boolean }) => Promise<void>;
  retour: () => Promise<void>;
  montrer: (selecteur: string) => void;
  chemin: () => string;
};

const attendre = (ms: number) => new Promise((r) => setTimeout(r, ms));
const pilote = (f: HTMLIFrameElement | null) =>
  (f?.contentWindow as (Window & { __carnet?: Pilote }) | null | undefined)?.__carnet;

type Scenario = { depart: string; arrivee: string; etat?: unknown; montrer?: string };

type NomTransition = "voyage" | "photo" | "jour" | "page";

const NOMS: Record<NomTransition, string> = {
  voyage: "T1 · Carte du voyage → en-tête",
  photo: "T2 · Miniature → plein écran → retour",
  jour: "T3 · Jour suivant, puis retour",
  page: "T4 · Autres pages (voyage ↔ jour)",
};

export default function LaboPage() {
  useTitre("Labo des transitions");
  const { data: voyages } = useVoyages();
  const slug = voyages?.[0]?.slug ?? "";
  const { data: voyage } = useVoyage(slug, !!slug);
  const jours = voyage?.jours ?? [];
  const j1 = jours[1]?.date ?? jours[0]?.date ?? "";
  const j2 = jours[2]?.date ?? jours[1]?.date ?? "";
  const { data: jour } = useJour(slug, j1, !!j1);
  const photo = jour?.photos[0];

  const [r, setR] = useState<Reglages>(() => reglages());
  const [enCours, setEnCours] = useState<string | null>(null);
  const tel = useRef<HTMLIFrameElement>(null);
  const pc = useRef<HTMLIFrameElement>(null);
  const reglagesCourants = useRef(r);

  const changer = (nouveaux: Reglages) => {
    reglagesCourants.current = nouveaux;
    setR(nouveaux);
    enregistrerReglages(nouveaux);
  };

  // Les réglages sont aussi lus par cette page : on les remet à jour si un
  // autre onglet les change.
  useEffect(() => {
    const surStockage = () => setR(reglages());
    window.addEventListener("storage", surStockage);
    return () => window.removeEventListener("storage", surStockage);
  }, []);

  const scenarios: Record<NomTransition, Scenario> | null =
    slug && j1 && j2 && photo
      ? {
          voyage: { depart: "/", arrivee: chemins.voyage(slug), montrer: `[data-transition-id="${idVoyage(slug)}"]` },
          photo: {
            depart: chemins.jour(slug, j1),
            arrivee: chemins.photo(slug, j1, photo.id),
            etat: { depuisJour: true },
            montrer: `[data-transition-id="${idPhoto(photo.id)}"]`,
          },
          jour: { depart: chemins.jour(slug, j1), arrivee: chemins.jour(slug, j2) },
          page: { depart: chemins.voyage(slug), arrivee: chemins.jour(slug, j1) },
        }
      : null;

  // Sur un téléphone, le cadre « ordinateur » n'est pas affiché (ni chargé).
  const [avecPc] = useState(() => window.matchMedia("(min-width: 900px)").matches);
  const cadres = () => [tel.current, pc.current].map(pilote).filter((p): p is Pilote => !!p);
  const pause = () => 1700 * reglagesCourants.current.ralenti;

  /** Place les iframes au point de départ, sans animation parasite visible ensuite. */
  async function preparer(s: Scenario) {
    const ps = cadres();
    await Promise.all(ps.map((p) => (p.chemin() === s.depart ? undefined : p.naviguer(s.depart, { replace: true }))));
    await attendre(900 * reglagesCourants.current.ralenti);
    if (s.montrer) ps.forEach((p) => p.montrer(s.montrer!));
    await attendre(250);
  }

  async function allerRetour(nom: NomTransition) {
    const s = scenarios?.[nom];
    if (!s) return;
    await preparer(s);
    await Promise.all(cadres().map((p) => p.naviguer(s.arrivee, { state: s.etat, preventScrollReset: nom === "photo" })));
    await attendre(pause());
    await Promise.all(cadres().map((p) => p.retour()));
    await attendre(pause());
  }

  async function lancer(nom: NomTransition) {
    if (enCours) return;
    setEnCours(nom);
    try {
      await allerRetour(nom);
    } finally {
      setEnCours(null);
    }
  }

  return (
    <div className={styles.labo}>
      <aside className={styles.panneau}>
        <h1 className={styles.titre}>Labo des transitions</h1>
        <p className={styles.aide}>
          Le vrai site tourne dans les cadres. « Rejouer » fait l'aller, puis le retour du navigateur.
          Sur téléphone, ouvre aussi le site directement pour juger au doigt.
        </p>

        <div className={styles.globaux}>
          <label>
            Ralenti{" "}
            <select
              value={r.ralenti}
              onChange={(e) => changer({ ...r, ralenti: Number(e.target.value) })}
            >
              <option value={1}>× 1 (réel)</option>
              <option value={2}>× 2</option>
              <option value={4}>× 4</option>
            </select>
          </label>
          <label>
            <input type="checkbox" checked={r.reduit} onChange={(e) => changer({ ...r, reduit: e.target.checked })} />{" "}
            Réduire les animations
          </label>
          <button type="button" onClick={() => changer(REGLAGES_DEFAUT)}>
            Valeurs par défaut
          </button>
        </div>

        {(Object.keys(NOMS) as NomTransition[]).map((nom) => (
          <section key={nom} className={styles.transition} data-en-cours={enCours === nom || undefined}>
            <h2>{NOMS[nom]}</h2>
            <div className={styles.actions}>
              <button type="button" disabled={!scenarios || !!enCours} onClick={() => lancer(nom)}>
                {enCours === nom ? "…" : "▶ Rejouer"}
              </button>
            </div>
          </section>
        ))}
        {!scenarios && <p className={styles.aide}>Chargement du voyage (il faut au moins deux jours et une photo)…</p>}
      </aside>

      <div className={styles.ecrans}>
        <figure className={styles.ecranTel}>
          <iframe ref={tel} src="/" title="Site, format téléphone" />
          <figcaption>Téléphone · 390 × 844</figcaption>
        </figure>
        {avecPc && (
          <figure className={styles.ecranPc}>
            <div className={styles.cadrePc}>
              <iframe ref={pc} src="/" title="Site, format ordinateur" />
            </div>
            <figcaption>Ordinateur · 1280 × 800 (réduit)</figcaption>
          </figure>
        )}
      </div>
    </div>
  );
}
