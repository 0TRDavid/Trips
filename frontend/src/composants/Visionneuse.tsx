import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import type { PhotoJour } from "../api/types";
import { useGlissement } from "../hooks/useGlissement";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { useTouchesClavier } from "../hooks/useTouchesClavier";
import { dateCourte, heureLocale } from "../lib/dates";
import { srcset } from "../lib/rendus";
import { idPhoto } from "../lib/transitions";
import { aUneVideo, formatDuree } from "../lib/videos";
import LecteurVideo from "./LecteurVideo";
import Photo from "./Photo";
import PhotoAnimee from "./PhotoAnimee";
import styles from "./Visionneuse.module.css";

type Props = {
  photos: PhotoJour[];
  /** -1 si la photo demandée n'appartient pas à ce jour. */
  index: number;
  date: string;
  precedent: () => void;
  suivant: () => void;
  fermer: () => void;
};

/** Précharge une photo voisine avec les mêmes srcset/sizes que l'affichage. */
function precharger(photo: PhotoJour | undefined) {
  if (!photo) return;
  const img = new Image();
  img.sizes = "100vw";
  img.srcset = srcset(photo);
}

/** Photo en plein écran, par-dessus la page jour. */
export default function Visionneuse({ photos, index, date, precedent, suivant, fermer }: Props) {
  const photo = photos[index];
  const aPrecedent = index > 0;
  const aSuivant = index >= 0 && index < photos.length - 1;
  const boutonFermer = useRef<HTMLButtonElement>(null);
  const dialogue = useRef<HTMLDivElement>(null);
  const mouvementReduit = useMouvementReduit();
  // « Réduire les animations » : une photo animée reste fixe ; le bouton
  // « Animer » la joue une fois (chaque clic remonte le composant, donc rejoue).
  // Le compteur est lié à la photo : on repart de zéro en changeant de photo.
  const [animations, setAnimations] = useState({ id: -1, n: 0 });
  const nbAnimations = animations.id === photo?.id ? animations.n : 0;

  useTouchesClavier({
    Escape: fermer,
    ArrowLeft: () => aPrecedent && precedent(),
    ArrowRight: () => aSuivant && suivant(),
  });

  const glissement = useGlissement((d) => {
    if (d === "suivant" && aSuivant) suivant();
    if (d === "precedent" && aPrecedent) precedent();
  });

  // Ouverture : bloque le défilement de la page dessous, place le focus dans
  // la visionneuse ; fermeture : rend le focus à l'élément d'origine.
  useEffect(() => {
    const avant = document.activeElement as HTMLElement | null;
    document.documentElement.classList.add("sans-defilement");
    // focusVisible: false : pas d'anneau de focus quand on ouvre à la souris.
    boutonFermer.current?.focus({ preventScroll: true, focusVisible: false } as FocusOptions);
    return () => {
      document.documentElement.classList.remove("sans-defilement");
      avant?.focus?.({ preventScroll: true });
    };
  }, []);

  useEffect(() => {
    precharger(photos[index + 1]);
    precharger(photos[index - 1]);
  }, [photos, index]);

  // Garde le focus clavier (Tab) à l'intérieur de la visionneuse.
  const pieger = (e: ReactKeyboardEvent) => {
    if (e.key !== "Tab" || !dialogue.current) return;
    const focusables = [
      ...dialogue.current.querySelectorAll<HTMLElement>("button:not(:disabled), a[href], video[controls]"),
    ];
    if (focusables.length === 0) return;
    const premier = focusables[0];
    const dernier = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === premier) {
      e.preventDefault();
      dernier.focus();
    } else if (!e.shiftKey && document.activeElement === dernier) {
      e.preventDefault();
      premier.focus();
    }
  };

  const nature = photo?.type === "video" ? "Vidéo" : "Photo";
  const libelle = photo ? `${nature} ${index + 1} sur ${photos.length}` : "Photo introuvable";
  const alt = photo ? photo.legende || `${nature} du ${dateCourte(date)}` : "";
  const animee = photo?.type === "animee" && aUneVideo(photo);

  return (
    <div
      ref={dialogue}
      className={styles.visionneuse}
      role="dialog"
      aria-modal="true"
      aria-label={libelle}
      onKeyDown={pieger}
    >
      <div className={styles.barre}>
        <span className={styles.compteur}>{photo ? `${index + 1} / ${photos.length}` : ""}</span>
        {animee && mouvementReduit && (
          <button
            type="button"
            className={styles.animer}
            onClick={() => setAnimations({ id: photo.id, n: nbAnimations + 1 })}
          >
            Animer
          </button>
        )}
        <button ref={boutonFermer} type="button" className={styles.fermer} onClick={fermer} aria-label="Fermer (Échap)">
          ✕
        </button>
      </div>

      <div className={styles.scene} {...glissement}>
        {photo?.type === "video" ? (
          <LecteurVideo key={photo.id} photo={photo} alt={alt} transitionId={idPhoto(photo.id)} />
        ) : animee ? (
          <PhotoAnimee
            key={`${photo.id}-${nbAnimations}`}
            photo={photo}
            mode="contenir"
            sizes="100vw"
            priorite
            alt={alt}
            transitionId={idPhoto(photo.id)}
            petitCote={Math.min(window.innerWidth, window.innerHeight)}
            forcer={nbAnimations > 0}
          />
        ) : photo ? (
          <Photo
            key={photo.id}
            photo={photo}
            mode="contenir"
            sizes="100vw"
            priorite
            alt={alt}
            transitionId={idPhoto(photo.id)}
          />
        ) : (
          <p className={styles.introuvable}>Cette photo n’existe pas dans ce jour.</p>
        )}
        {aPrecedent && (
          <button type="button" className={styles.fleche} data-sens="precedent" onClick={precedent} aria-label="Photo précédente (←)">
            ‹
          </button>
        )}
        {aSuivant && (
          <button type="button" className={styles.fleche} data-sens="suivant" onClick={suivant} aria-label="Photo suivante (→)">
            ›
          </button>
        )}
      </div>

      <div className={styles.legende}>
        {photo && (
          <>
            {photo.legende && <p className={styles.texteLegende}>{photo.legende}</p>}
            <p className={styles.quand}>
              {dateCourte(date)}
              {photo.prise_le && ` · ${heureLocale(photo.prise_le)}`}
              {photo.type === "video" && photo.duree != null && ` · vidéo ${formatDuree(photo.duree)}`}
              {photo.photographe && ` · ${photo.photographe}`}
              {photo.favori && " · ★"}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
