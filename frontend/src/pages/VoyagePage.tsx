import { lazy, Suspense, useCallback, useMemo, useState } from "react";
import { useParams } from "react-router";
import { useVoyage } from "../api/requetes";
import Apparition from "../composants/Apparition";
import EnteteVoyage from "../composants/EnteteVoyage";
import Recit from "../composants/Recit";
import TimelineJours from "../composants/TimelineJours";
import { useApresVol, usePalette } from "../layout/contexte";
import { EtatChargement, EtatErreur } from "../layout/Etats";
import { dateCourte } from "../lib/dates";
import styles from "./VoyagePage.module.css";

// MapLibre pèse ~1 Mo : chargé seulement sur la page voyage, pas sur
// l'accueil ni les jours. Sa zone a déjà sa taille : rien ne bouge à l'arrivée.
const CarteParcours = lazy(() => import("../composants/CarteParcours"));

export default function VoyagePage() {
  const { slug = "" } = useParams();
  const { data: voyage, error, refetch, isPending, isPlaceholderData } = useVoyage(slug);
  usePalette(voyage?.palette);
  // La carte (la plus lourde à monter) attend que la couverture ait fini de
  // voler depuis l'accueil ; sa place est déjà réservée, rien ne bouge.
  const carteAutorisee = useApresVol();
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

  // Les blocs sous l'en-tête apparaissent en cascade (<Apparition>) ; tant que
  // seul le résumé venu de l'accueil est là, leur place reste vide.
  return (
    <article className={styles.page}>
      <EnteteVoyage voyage={voyage} />

      {!isPlaceholderData && voyage.recit_intro_html.trim() && (
        <Apparition className={styles.intro}>
          <section>
            <Recit html={voyage.recit_intro_html} />
          </section>
        </Apparition>
      )}

      {!isPlaceholderData && (
      <Apparition className={styles.parcours}>
        <section className={styles.colCarte} aria-labelledby="titre-carte">
        <h2 id="titre-carte" className={styles.titreSection}>
          Le parcours
        </h2>
        <div className={styles.zoneCarte}>
          {voyage.trace.length > 0 ? (
            <>
              {carteAutorisee && (
              <Suspense fallback={null}>
                <CarteParcours
                  trace={voyage.trace}
                  selection={selection}
                  surSelection={selectionDepuisCarte}
                />
              </Suspense>
              )}
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
        </section>

        <section className={styles.jours} aria-labelledby="titre-jours">
          <h2 id="titre-jours" className={styles.titreSection}>
            Jour après jour
          </h2>
          {/* En variante E (ordinateur), seule cette liste défile : le titre reste. */}
          <div className={styles.defilement}>
          <TimelineJours
            slug={voyage.slug}
            debut={voyage.date_debut}
            jours={voyage.jours}
            joursLocalises={joursLocalises}
            selection={selection}
            surSelection={selectionDepuisListe}
          />
          </div>
        </section>
      </Apparition>
      )}
    </article>
  );
}
