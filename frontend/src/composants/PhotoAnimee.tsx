import { useEffect, useRef, useState } from "react";
import type { ComponentProps } from "react";
import type { PhotoJour } from "../api/types";
import { useChefDeLecture } from "../hooks/useLecture";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { sourceVideo } from "../lib/videos";
import Photo from "./Photo";
import styles from "./PhotoAnimee.module.css";

type Props = Omit<ComponentProps<typeof Photo>, "photo" | "children"> & {
  photo: PhotoJour;
  /** Petit côté affiché, en px CSS : choisit le 720p ou le 1080p. */
  petitCote?: number;
  /** Anime même si le système demande de réduire les animations (choix explicite). */
  forcer?: boolean;
};

/**
 * Photo animée : l'image fixe (via <Photo>, avec sa couleur et son flou), et
 * par-dessus sa courte vidéo, sans son, jouée UNE fois quand la photo apparaît
 * à l'écran, puis retour en fondu à l'image fixe.
 *
 * - Rien n'est téléchargé avant la première apparition à l'écran (src posé
 *   à ce moment-là, preload="none") ;
 * - lecture quand la moitié de la photo est visible, pause si elle sort avant
 *   la fin (reprise au retour) ; une fois finie, elle ne rejoue plus (un
 *   nouveau montage du composant la rejoue : ouverture dans la visionneuse) ;
 * - la vidéo apparaît en fondu une fois la lecture vraiment commencée, et
 *   disparaît en fondu à la fin : jamais d'écran noir ;
 * - « réduire les animations » : aucune vidéo, l'image reste fixe (sauf
 *   `forcer`, quand on a demandé l'animation) ;
 * - dans la galerie d'un jour (chef de lecture, lib/lecture.ts) : une seule
 *   photo animée joue à la fois, celle la plus proche du centre de l'écran ;
 *   seule l'élue télécharge sa vidéo. Hors galerie (visionneuse), chaque
 *   photo animée joue dès qu'elle est visible, comme avant.
 */
export default function PhotoAnimee({ photo, petitCote = 400, forcer = false, ...props }: Props) {
  const mouvementReduit = useMouvementReduit();
  const anime = forcer || !mouvementReduit;
  const video = useRef<HTMLVideoElement>(null);
  const [visible, setVisible] = useState(false);
  const [dejaVue, setDejaVue] = useState(false);
  const [enLecture, setEnLecture] = useState(false);
  const [terminee, setTerminee] = useState(false);
  const chef = useChefDeLecture();
  const densite = typeof window === "undefined" ? 1 : window.devicePixelRatio || 1;
  const source = sourceVideo(photo, petitCote, densite);

  // Animation coupée (bouton « Arrêter ») : au retour, la vidéo repartira
  // invisible jusqu'à sa vraie reprise.
  useEffect(() => {
    if (!anime) setEnLecture(false);
  }, [anime]);

  // Galerie : c'est le chef de lecture qui dit quand jouer (« élue »).
  useEffect(() => {
    const element = video.current;
    if (!element || !chef || forcer || terminee) return;
    return chef.inscrire(element, (elue) => {
      setVisible(elue);
      if (elue) setDejaVue(true);
    });
  }, [chef, forcer, terminee, anime]);

  // Hors galerie : visibilité à l'écran (IntersectionObserver : le navigateur
  // nous prévient, sans calcul au défilement).
  useEffect(() => {
    const element = video.current;
    if (!element || (chef && !forcer)) return;
    const observateur = new IntersectionObserver(
      ([entree]) => {
        setVisible(entree.isIntersecting);
        if (entree.isIntersecting) setDejaVue(true);
      },
      { threshold: 0.5 },
    );
    observateur.observe(element);
    return () => observateur.disconnect();
  }, [anime, chef, forcer]);

  // Lecture / pause selon la visibilité.
  useEffect(() => {
    const element = video.current;
    if (!element) return;
    if (terminee) return;
    if (visible && dejaVue) {
      // play() échoue si le navigateur refuse (économie d'énergie…) : l'image fixe reste.
      element.play().catch((e: unknown) => {
        setEnLecture(false);
        // Lecture refusée (économie d'énergie) : dans la galerie, on rend la
        // main à la suivante plutôt que de garder une élue qui ne joue pas.
        if (chef && (e as { name?: string })?.name === "NotAllowedError") setTerminee(true);
      });
    } else {
      element.pause();
    }
  }, [visible, dejaVue, terminee, source?.url, anime, chef]);

  return (
    <Photo photo={photo} {...props}>
      {anime && source && (
        <video
          ref={video}
          className={styles.video}
          src={dejaVue ? source.url : undefined}
          muted
          playsInline
          preload="none"
          disablePictureInPicture
          disableRemotePlayback
          aria-hidden="true"
          tabIndex={-1}
          data-lecture={enLecture || undefined}
          onPlaying={() => setEnLecture(true)}
          onEnded={() => {
            setEnLecture(false);
            setTerminee(true);
          }}
        />
      )}
    </Photo>
  );
}
