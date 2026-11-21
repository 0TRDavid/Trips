import { useCallback, useEffect } from "react";
import { useLocation, useNavigate, useParams } from "react-router";
import { useJour } from "../api/requetes";
import Visionneuse from "../composants/Visionneuse";
import { chemins } from "../lib/chemins";
import { idPhoto } from "../lib/transitions";

type EtatHistorique = { depuisJour?: boolean } | null;

/**
 * Logique de navigation de la visionneuse. Les données viennent du cache de
 * la page jour (même requête) : aucune requête supplémentaire.
 *
 * Historique :
 * - ouvrir une photo depuis la galerie ajoute une entrée ;
 * - ← / → remplacent l'entrée courante : « retour » ferme la visionneuse au
 *   lieu de repasser par toutes les photos vues ;
 * - fermer revient à l'entrée de la page jour (history.back) si on vient
 *   d'elle, sinon (lien direct) remplace l'URL par celle du jour.
 */
export default function VisionneusePage() {
  const { slug = "", date = "", photoId = "" } = useParams();
  const { data: jour } = useJour(slug, date);
  const navigate = useNavigate();
  const location = useLocation();
  const etat = location.state as EtatHistorique;

  const photos = jour?.photos ?? [];
  const index = photos.findIndex((p) => String(p.id) === photoId);

  const aller = useCallback(
    (nouvelIndex: number) => {
      const p = photos[nouvelIndex];
      if (!p) return;
      navigate(chemins.photo(slug, date, p.id), {
        replace: true,
        preventScrollReset: true,
        state: etat,
      });
    },
    [photos, navigate, slug, date, etat],
  );

  const fermer = useCallback(() => {
    if (etat?.depuisJour) navigate(-1);
    else navigate(chemins.jour(slug, date), { replace: true, preventScrollReset: true });
  }, [etat, navigate, slug, date]);

  // À la fermeture, ramène à l'écran la miniature de la dernière photo vue
  // (on a pu en parcourir beaucoup). Après la restauration du défilement.
  useEffect(() => {
    return () => {
      requestAnimationFrame(() => {
        document
          .querySelector(`[data-transition-id="${idPhoto(Number(photoId))}"]`)
          ?.scrollIntoView({ block: "nearest" });
      });
    };
  }, [photoId]);

  if (!jour) return null; // la page jour affiche déjà le chargement
  return (
    <Visionneuse
      photos={photos}
      index={index}
      date={jour.date}
      depuisGalerie={etat?.depuisJour === true}
      precedent={() => aller(index - 1)}
      suivant={() => aller(index + 1)}
      fermer={fermer}
    />
  );
}
