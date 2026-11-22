import { useEffect, useRef } from "react";
import type { PhotoJour } from "../api/types";
import { srcParDefaut } from "../lib/rendus";
import { sourceVideo } from "../lib/videos";
import styles from "./VideoGalerie.module.css";

type Props = {
  photo: PhotoJour;
  /** Petit côté de la case, en px CSS : choisit le 720p ou le 1080p. */
  petitCote: number;
};

/**
 * Vidéo lue sur place dans la galerie d'un jour, au clic sur sa case (pas
 * de visionneuse) : posée dans <Photo> (prop children), elle recouvre
 * exactement l'aperçu, avec le son et les contrôles du navigateur.
 *
 * - une seule vidéo de galerie joue à la fois (lancer l'une met les autres en pause) ;
 * - pause dès qu'elle quitte l'écran à moitié (page suivante) ;
 * - pause sous la visionneuse : GaleriePhotos (`suspendu`).
 */
export default function VideoGalerie({ photo, petitCote }: Props) {
  const video = useRef<HTMLVideoElement>(null);
  const source = sourceVideo(photo, petitCote, window.devicePixelRatio || 1);

  useEffect(() => {
    const v = video.current;
    if (!v) return;
    // Le clic qui l'a montée autorise la lecture avec le son.
    v.play().catch(() => {});
    const observateur = new IntersectionObserver(
      ([e]) => {
        if (e.intersectionRatio < 0.5) v.pause();
      },
      // root: document, sinon faux dans les iframes du labo.
      { root: document, threshold: [0, 0.5] },
    );
    observateur.observe(v);
    return () => observateur.disconnect();
  }, []);

  if (!source) return null;
  return (
    <video
      ref={video}
      className={styles.video}
      src={source.url}
      poster={srcParDefaut(photo)}
      controls
      playsInline
      data-video-galerie=""
      onPlay={(e) => {
        for (const autre of document.querySelectorAll<HTMLVideoElement>("video[data-video-galerie]")) {
          if (autre !== e.currentTarget) autre.pause();
        }
      }}
    />
  );
}
