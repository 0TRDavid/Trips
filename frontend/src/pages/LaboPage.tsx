import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useJour, useVoyage, useVoyages } from "../api/requetes";
import { useTitre } from "../hooks/useTitre";
import { chemins } from "../lib/chemins";
import type { Reglages } from "../lib/mouvement";
import {
  REGLAGES_DEFAUT,
  VARIANTES_APPARITION,
  VARIANTES_COLLANT,
  VARIANTES_OUVERTURE,
  enregistrerReglages,
  reglages,
} from "../lib/mouvement";
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
  defiler: (vitesse: number) => Promise<void>;
};

const attendre = (ms: number) => new Promise((r) => setTimeout(r, ms));
const pilote = (f: HTMLIFrameElement | null) =>
  (f?.contentWindow as (Window & { __carnet?: Pilote }) | null | undefined)?.__carnet;

type Scenario = { depart: string; arrivee: string; etat?: unknown; montrer?: string };

type NomTransition = "voyage" | "photo" | "jour" | "page" | "defilement";

const NOMS: Record<NomTransition, string> = {
  voyage: "T1 · Carte du voyage → en-tête",
  photo: "T2 · Miniature → plein écran → retour",
  jour: "T3 · Jour suivant, puis retour",
  page: "T4 · Vignette de la timeline → en-tête du jour",
  defilement: "T5 · Défilement de la journée la plus chargée",
};

const LIBELLES: Record<string, string> = {
  aucune: "aucune",
  fondu: "fondu",
  montee: "montée",
  cascade: "cascade",
  pousse: "chaque heure poussée par la suivante",
  bandeau: "bandeau unique",
  efface: "s'efface en glissant",
  decale: "glisse seulement",
};

/** Vitesses de lecture de T5, en px/s. */
const VITESSES = [300, 600, 1200] as const;

/** Taille simulée du cadre « ordinateur ». */
const ECRANS = [
  { l: 1280, h: 800 },
  { l: 1920, h: 1080 },
  { l: 2560, h: 1440 },
] as const;
const LARGEUR_AFFICHEE = 900;

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
  // T5 : la journée qui a le plus de photos.
  const plusChargee = jours.reduce<(typeof jours)[number] | undefined>(
    (m, j) => (!m || j.nb_photos > m.nb_photos ? j : m),
    undefined,
  )?.date;
  const [vitesse, setVitesse] = useState<number>(600);

  const [r, setR] = useState<Reglages>(() => reglages());
  const [enCours, setEnCours] = useState<string | null>(null);
  const [ecran, setEcran] = useState(1);
  const { l: ecranL, h: ecranH } = ECRANS[ecran];
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
          defilement: { depart: chemins.jour(slug, plusChargee ?? j1), arrivee: "" },
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

  /** T5 : recharge la journée (rien de déjà vu), puis la fait défiler jusqu'en bas. */
  async function defiler() {
    const s = scenarios?.defilement;
    if (!s) return;
    const ps = cadres();
    await Promise.all(ps.map((p) => p.naviguer("/", { replace: true })));
    await attendre(300);
    await Promise.all(ps.map((p) => p.naviguer(s.depart, { replace: true })));
    await attendre(1200 * reglagesCourants.current.ralenti);
    await Promise.all(ps.map((p) => p.defiler(vitesse / reglagesCourants.current.ralenti)));
  }

  async function lancer(nom: NomTransition) {
    if (enCours) return;
    setEnCours(nom);
    try {
      if (nom === "defilement") await defiler();
      else await allerRetour(nom);
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

        <div className={styles.globaux}>
          <strong>Page jour</strong>
          {(
            [
              ["apparition", "Apparition des photos", VARIANTES_APPARITION],
              ["collant", "Heure collante", VARIANTES_COLLANT],
              ["ouverture", "Photo d'ouverture", VARIANTES_OUVERTURE],
            ] as const
          ).map(([cle, libelle, valeurs]) => (
            <label key={cle}>
              {libelle}{" "}
              <select value={r[cle]} onChange={(e) => changer({ ...r, [cle]: e.target.value })}>
                {valeurs.map((v) => (
                  <option key={v} value={v}>
                    {LIBELLES[v] ?? v}
                    {v === REGLAGES_DEFAUT[cle] ? " (défaut)" : ""}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <label>
            Vitesse de T5{" "}
            <select value={vitesse} onChange={(e) => setVitesse(Number(e.target.value))}>
              {VITESSES.map((v) => (
                <option key={v} value={v}>
                  {v} px/s
                </option>
              ))}
            </select>
          </label>
          <p className={styles.aide}>Ces variantes s'appliquent à la prochaine page jour affichée (T5 la recharge).</p>
        </div>

        {avecPc && (
          <label className={styles.globaux}>
            Écran ordinateur{" "}
            <select value={ecran} onChange={(e) => setEcran(Number(e.target.value))}>
              {ECRANS.map((e, i) => (
                <option key={e.l} value={i}>
                  {e.l} × {e.h}
                </option>
              ))}
            </select>
          </label>
        )}

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
          <figure
            className={styles.ecranPc}
            style={
              {
                "--ecran-l": `${ecranL}px`,
                "--ecran-h": `${ecranH}px`,
                "--echelle": LARGEUR_AFFICHEE / ecranL,
              } as CSSProperties
            }
          >
            <div className={styles.cadrePc}>
              <iframe ref={pc} src="/" title="Site, format ordinateur" />
            </div>
            <figcaption>
              Ordinateur · {ecranL} × {ecranH} (réduit)
            </figcaption>
          </figure>
        )}
      </div>
    </div>
  );
}
