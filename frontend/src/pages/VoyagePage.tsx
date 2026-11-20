import { lazy, Suspense, useCallback, useMemo, useState } from "react";
import { useParams } from "react-router";
import { useVoyage } from "../api/requetes";
import EnteteVoyage from "../composants/EnteteVoyage";
import Recit from "../composants/Recit";
import TimelineJours from "../composants/TimelineJours";
import { EtatChargement, EtatErreur } from "../layout/Etats";
import { dateCourte } from "../lib/dates";
import styles from "./VoyagePage.module.css";

// MapLibre pèse ~1 Mo : chargé seulement sur la page voyage, pas sur
// l'accueil ni les jours. Sa zone a déjà sa taille : rien ne bouge à l'arrivée.
const CarteParcours = lazy(() => import("../composants/CarteParcours"));

export default function VoyagePage() {
  const { slug = "" } = useParams();
  const { data: voyage, error, refetch, isPending } = useVoyage(slug);
  // Jour sélectionné (zoom de la carte). État d'écran éphémère, pas dans
  // l'URL : le retour arrière ramène à la page précédente, pas au zoom d'avant.
  const [selection, setSelection] = useState<string | null>(null);

  const joursLocalises = useMemo(() => new Set(voyage?.trace.map((p) => p.jour)), [voyage]);

  // Clic sur un point de la carte : on sélectionne le jour et on l'amène à
  // l'écran dans la liste.
  const selectionDepuisCarte = useCallback((jour: string) => {
    setSelection(jour);
    document
      .querySelector(`[data-jour="${jour}"]`)
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, []);

  // Re-cliquer un jour sélectionné revient à la vue d'ensemble.
  const selectionDepuisListe = useCallback(
    (jour: string) => setSelection((s) => (s === jour ? null : jour)),
    [],
  );

  if (isPending) return <EtatChargement />;
  if (error) return <EtatErreur erreur={error} reessayer={refetch} />;

  return (
    <article className={styles.page}>
      <EnteteVoyage voyage={voyage} />

      {voyage.recit_intro_html.trim() && (
        <section className={styles.intro}>
          <Recit html={voyage.recit_intro_html} />
        </section>
      )}

      <div className={styles.parcours}>
        <div className={styles.zoneCarte}>
          {voyage.trace.length > 0 ? (
            <>
              <Suspense fallback={null}>
                <CarteParcours
                  trace={voyage.trace}
                  selection={selection}
                  surSelection={selectionDepuisCarte}
                />
              </Suspense>
              <div className={styles.etiquette} aria-live="polite">
                {selection ? (
                  <>
                    <span>
                      {dateCourte(selection)}
                      {!joursLocalises.has(selection) && " · pas de position"}
                    </span>
                    <button type="button" onClick={() => setSelection(null)}>
                      Tout le voyage
                    </button>
                  </>
                ) : (
                  <span>Tout le voyage</span>
                )}
              </div>
            </>
          ) : (
            <p className={styles.sansCarte}>Aucune photo géolocalisée pour ce voyage.</p>
          )}
        </div>

        <section className={styles.jours} aria-labelledby="titre-jours">
          <h2 id="titre-jours" className={styles.titreJours}>
            Jour après jour
          </h2>
          <TimelineJours
            slug={voyage.slug}
            debut={voyage.date_debut}
            jours={voyage.jours}
            joursLocalises={joursLocalises}
            selection={selection}
            surSelection={selectionDepuisListe}
          />
        </section>
      </div>
    </article>
  );
}
