import { useState } from "react";
import type { PhotoJour } from "../api/types";
import { srcParDefaut } from "../lib/rendus";
import { formatDuree, sourceVideo } from "../lib/videos";
import Photo from "./Photo";
import styles from "./LecteurVideo.module.css";

type Props = {
  photo: PhotoJour;
  alt: string;
  transitionId?: string;
};

/**
 * Vidéo dans la visionneuse : son image d'aperçu et un bouton ▶ ; au clic,
 * le lecteur du navigateur (avec le son) prend exactement la place de
 * l'aperçu. Rien n'est chargé avant le clic.
 *
 * Changer de média démonte le composant (clé = id dans la visionneuse) :
 * la lecture s'arrête d'elle-même.
 */
export default function LecteurVideo({ photo, alt, transitionId }: Props) {
  const [lecture, setLecture] = useState(false);
  const petitCote = Math.min(window.innerWidth, window.innerHeight);
  const source = sourceVideo(photo, petitCote, window.devicePixelRatio || 1);
  const duree = formatDuree(photo.duree);

  return (
    <Photo photo={photo} mode="contenir" sizes="100vw" priorite alt={alt} transitionId={transitionId}>
      {lecture && source ? (
        <video
          className={styles.video}
          src={source.url}
          poster={srcParDefaut(photo)}
          controls
          autoPlay
          playsInline
          // Les gestes sur les contrôles (barre de progression) ne changent pas de média.
          data-sans-glissement
        />
      ) : (
        <button
          type="button"
          className={styles.lire}
          onClick={() => setLecture(true)}
          disabled={!source}
          aria-label={source ? `Lire la vidéo${duree ? ` (${duree})` : ""}` : "Vidéo en préparation"}
        >
          <span className={styles.icone} aria-hidden="true">
            ▶
          </span>
          {duree && <span className={styles.duree}>{duree}</span>}
        </button>
      )}
    </Photo>
  );
}
