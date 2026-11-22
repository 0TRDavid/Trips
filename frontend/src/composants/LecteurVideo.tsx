import { useEffect, useRef, useState } from "react";
import type { PhotoJour } from "../api/types";
import { srcParDefaut } from "../lib/rendus";
import { formatDuree, sourceVideo } from "../lib/videos";
import Photo from "./Photo";
import styles from "./LecteurVideo.module.css";

type Props = {
  photo: PhotoJour;
  alt: string;
  transitionId?: string;
  /** Attente avant le départ automatique (s) : le temps que la miniature finisse de voler. */
  delaiDepart?: number;
};

/**
 * Vidéo dans la visionneuse : elle part toute seule (avec le son) dès
 * l'ouverture, une fois le vol de la miniature terminé ; le lecteur du
 * navigateur prend exactement la place de l'aperçu (même image en poster).
 * Si le navigateur refuse la lecture automatique (page ouverte directement
 * par son adresse, sans clic), on revient à l'aperçu et à son bouton ▶.
 *
 * Changer de média démonte le composant (clé = id dans la visionneuse) :
 * la lecture s'arrête d'elle-même.
 */
export default function LecteurVideo({ photo, alt, transitionId, delaiDepart = 0 }: Props) {
  const [lecture, setLecture] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const petitCote = Math.min(window.innerWidth, window.innerHeight);
  const source = sourceVideo(photo, petitCote, window.devicePixelRatio || 1);
  const duree = formatDuree(photo.duree);

  // Départ automatique, après le vol d'ouverture.
  useEffect(() => {
    if (!source) return;
    const minuterie = setTimeout(() => setLecture(true), delaiDepart * 1000);
    return () => clearTimeout(minuterie);
    // Au montage seulement : un autre média remonte le composant.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!lecture) return;
    video.current?.play().catch((e: unknown) => {
      // Lecture automatique refusée : l'aperçu et son bouton ▶ reviennent.
      if (e instanceof DOMException && e.name === "NotAllowedError") setLecture(false);
    });
  }, [lecture]);

  return (
    <Photo photo={photo} mode="contenir" sizes="100vw" priorite alt={alt} transitionId={transitionId}>
      {lecture && source ? (
        <video
          ref={video}
          className={styles.video}
          src={source.url}
          poster={srcParDefaut(photo)}
          controls
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
