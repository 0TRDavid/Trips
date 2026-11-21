import { useRef } from "react";
import { Link } from "react-router";
import { prechargerJour } from "../api/requetes";
import type { JourResume } from "../api/types";
import { useVolEntrant } from "../hooks/useVolEntrant";
import { useNavigationPage } from "../layout/contexte";
import { chemins } from "../lib/chemins";
import { dateCourte, jourSemaine, numeroJour, pluriel } from "../lib/dates";
import { volEnTete } from "../lib/mouvement";
import { idJour } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./TimelineJours.module.css";

type Props = {
  slug: string;
  debut: string | null;
  jours: JourResume[];
  /** Jours qui ont au moins une position (zoom possible sur la carte). */
  joursLocalises: Set<string>;
  selection: string | null;
  surSelection: (date: string) => void;
};

/**
 * Les jours du voyage, l'un sous l'autre. Toucher un jour le sélectionne et
 * zoome la carte sur ses photos ; le lien « Ouvrir » mène à la page du jour.
 * Sur téléphone, le lien reste visible : la carte n'est jamais le seul
 * chemin vers un jour.
 */
export default function TimelineJours({ slug, debut, jours, joursLocalises, selection, surSelection }: Props) {
  return (
    <ol className={styles.liste}>
      {jours.map((jour) => {
        const actif = jour.date === selection;
        const n = numeroJour(debut, jour.date);
        const precharger = () => void prechargerJour(slug, jour.date);
        return (
          <li key={jour.date} className={styles.jour} data-jour={jour.date} data-actif={actif || undefined}>
            <button
              type="button"
              className={styles.selection}
              onClick={() => surSelection(jour.date)}
              aria-pressed={actif}
              aria-label={`${joursLocalises.has(jour.date) ? "Voir sur la carte" : "Sélectionner"} : ${dateCourte(jour.date)}${jour.titre ? `, ${jour.titre}` : ""}`}
            >
              <VignetteJour slug={slug} jour={jour} />
              <span className={styles.texte}>
                <span className={styles.date}>
                  {n !== null && <>Jour {n} · </>}
                  {jourSemaine(jour.date)} {dateCourte(jour.date)}
                </span>
                <span className={styles.titre}>{jour.titre || "Sans titre"}</span>
                <span className={styles.meta}>
                  {[jour.lieu, pluriel(jour.nb_photos, "photo")].filter(Boolean).join(" · ")}
                  {!joursLocalises.has(jour.date) && " · sans position"}
                </span>
              </span>
            </button>
            <Link
              to={chemins.jour(slug, jour.date)}
              className={styles.ouvrir}
              onPointerEnter={precharger}
              onFocus={precharger}
              onTouchStart={precharger}
              aria-label={`Ouvrir le ${dateCourte(jour.date)}`}
            >
              <span className={styles.libelleOuvrir}>Ouvrir </span><span aria-hidden>→</span>
            </Link>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Vignette d'un jour. Même transitionId que la couverture de la page du jour :
 * en revenant du jour, la couverture redescend s'y poser.
 */
function VignetteJour({ slug, jour }: { slug: string; jour: JourResume }) {
  const ref = useRef<HTMLSpanElement>(null);
  const nav = useNavigationPage();
  const id = idJour(slug, jour.date);
  useVolEntrant(
    id,
    () => ref.current,
    () => (nav.genre === "ouvrirJour" && nav.sens === -1 ? { transition: volEnTete(-1) } : null),
  );
  return (
    <span ref={ref} className={styles.vignette} data-transition-id={jour.photo ? id : undefined}>
      {jour.photo && <Photo photo={jour.photo} mode="couvrir" sizes="96px" alt="" />}
    </span>
  );
}
