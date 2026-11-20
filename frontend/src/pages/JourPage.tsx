import { useOutlet, useParams } from "react-router";
import { useJour } from "../api/requetes";
import EnteteJour from "../composants/EnteteJour";
import GaleriePhotos from "../composants/GaleriePhotos";
import NavJours from "../composants/NavJours";
import Recit from "../composants/Recit";
import { useTitre } from "../hooks/useTitre";
import { EtatChargement, EtatErreur } from "../layout/Etats";
import { dateCourte, estDateJour } from "../lib/dates";
import IntrouvablePage from "./IntrouvablePage";
import styles from "./JourPage.module.css";

export default function JourPage() {
  const { slug = "", date = "" } = useParams();
  const dateValide = estDateJour(date);
  const { data: jour, error, refetch, isPending } = useJour(slug, dateValide ? date : "invalide");
  // La visionneuse (route enfant) quand une photo est ouverte, sinon null.
  const visionneuse = useOutlet();

  useTitre(jour ? `${jour.titre || dateCourte(jour.date)} · ${jour.voyage.titre}` : undefined);

  if (!dateValide) return <IntrouvablePage />;
  if (isPending) return <EtatChargement />;
  if (error) return <EtatErreur erreur={error} reessayer={refetch} />;

  return (
    <>
      {/* inert : quand la visionneuse est ouverte, la page dessous n'est ni
          cliquable ni atteignable au clavier, mais reste affichée et montée. */}
      <article className={styles.page} inert={visionneuse !== null}>
        <EnteteJour jour={jour} />
        <Recit html={jour.recit_html} className={styles.recit} />
        {jour.photos.length > 0 ? (
          <GaleriePhotos slug={slug} date={jour.date} photos={jour.photos} />
        ) : (
          <p className={styles.vide}>Aucune photo visible pour ce jour.</p>
        )}
        <NavJours slug={slug} precedent={jour.precedent} suivant={jour.suivant} />
      </article>
      {visionneuse}
    </>
  );
}
