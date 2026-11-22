import { Fragment } from "react";
import { useOutlet, useParams } from "react-router";
import { AnimatePresence } from "motion/react";
import { useJour } from "../api/requetes";
import Apparition from "../composants/Apparition";
import EnteteJour from "../composants/EnteteJour";
import GaleriePhotos from "../composants/GaleriePhotos";
import NavJours from "../composants/NavJours";
import Recit from "../composants/Recit";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { useTitre } from "../hooks/useTitre";
import { useApresVol, usePalette } from "../layout/contexte";
import { EtatChargement, EtatErreur } from "../layout/Etats";
import { chemins } from "../lib/chemins";
import { dateCourte, estDateJour } from "../lib/dates";
import { galeriePleinEcran } from "../lib/rangees";
import IntrouvablePage from "./IntrouvablePage";
import styles from "./JourPage.module.css";

export default function JourPage() {
  const { slug = "", date = "" } = useParams();
  const dateValide = estDateJour(date);
  const { data: jour, error, refetch, isPending } = useJour(slug, dateValide ? date : "invalide");
  // La visionneuse (route enfant) quand une photo est ouverte, sinon null.
  const visionneuse = useOutlet();

  usePalette(jour?.palette);
  // En venant du voyage, la galerie (des dizaines de photos à monter) attend
  // que la couverture du jour ait fini de voler, puis apparaît en fondu.
  const galerieAutorisee = useApresVol();
  const reduit = useMouvementReduit();
  useTitre(jour ? `${jour.titre || dateCourte(jour.date)} · ${jour.voyage.titre}` : undefined);

  if (!dateValide) return <IntrouvablePage />;
  if (isPending) return <EtatChargement />;
  if (error) return <EtatErreur erreur={error} reessayer={refetch} />;

  // Galerie plein écran : le début du récit (avant tout marqueur [[14h]]) est
  // posé à droite de la couverture, révélé au premier cran de molette.
  const blocs = jour.recit_blocs;
  const surCouverture =
    galeriePleinEcran() && !reduit && jour.photos.length > 0 && blocs[0]?.heure === null && !!blocs[0].html.trim();

  return (
    <>
      {/* inert : quand la visionneuse est ouverte, la page dessous n'est ni
          cliquable ni atteignable au clavier, mais reste affichée et montée. */}
      <article className={styles.page} inert={visionneuse !== null}>
        <EnteteJour jour={jour} recit={surCouverture ? blocs[0].html : undefined} />
        {galerieAutorisee && (
          <Apparition className={styles.suite}>
            {jour.photos.length > 0 ? (
              // Le récit est dans la galerie, intercalé entre les heures (marqueurs [[14h]]).
              <GaleriePhotos
                slug={slug}
                date={jour.date}
                photos={jour.photos}
                blocs={surCouverture ? blocs.slice(1) : blocs}
                suivant={jour.suivant ? chemins.jour(slug, jour.suivant.date) : undefined}
                suspendu={visionneuse !== null}
              />
            ) : (
              <>
                <Recit html={jour.recit_html} />
                <p className={styles.vide}>Aucune photo visible pour ce jour.</p>
              </>
            )}
            <NavJours slug={slug} precedent={jour.precedent} suivant={jour.suivant} />
          </Apparition>
        )}
      </article>
      {/* AnimatePresence garde la visionneuse affichée pendant sa fermeture
          (retour de la photo vers sa miniature, Visionneuse.tsx). */}
      <AnimatePresence>{visionneuse && <Fragment key="visionneuse">{visionneuse}</Fragment>}</AnimatePresence>
    </>
  );
}
