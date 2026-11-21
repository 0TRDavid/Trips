import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { AnimatePresence, animate, motion, usePresence } from "motion/react";
import type { PhotoJour } from "../api/types";
import { useGlissement } from "../hooks/useGlissement";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { useTouchesClavier } from "../hooks/useTouchesClavier";
import { useVolEntrant } from "../hooks/useVolEntrant";
import { dateCourte, heureLocale } from "../lib/dates";
import type { Sens } from "../lib/mouvement";
import { fondu, transitionFondVisionneuse, variantesPhotoVoisine, volPhoto } from "../lib/mouvement";
import { consommerRetourDejaAnime } from "../lib/navigation";
import { srcset } from "../lib/rendus";
import { idPhoto } from "../lib/transitions";
import { lancerVol, selecteurTransition } from "../lib/vol";
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
  /** Ouverte depuis la galerie (et non par un lien direct) : la miniature grandit jusqu'ici. */
  depuisGalerie: boolean;
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

/** Miniature de la galerie (hors de la visionneuse) qui porte cet identifiant. */
function miniature(id: string, racine: Element): HTMLElement | null {
  for (const el of document.querySelectorAll<HTMLElement>(selecteurTransition(id))) {
    if (!racine.contains(el)) return el;
  }
  return null;
}

/**
 * Photo en plein écran, par-dessus la page jour.
 *
 * Mouvements (valeurs dans lib/mouvement.ts) :
 * - ouverture depuis la galerie : la miniature grandit jusqu'à sa place
 *   (lib/vol.ts) pendant que le fond noir apparaît ;
 * - photo → photo : glissement court dans le sens du parcours ;
 * - fermeture (✕, Échap, retour du navigateur) : la photo regagne sa
 *   miniature, ramenée à l'écran juste avant. La page jour la garde montée
 *   le temps du mouvement (AnimatePresence, usePresence).
 */
export default function Visionneuse({ photos, index, date, depuisGalerie, precedent, suivant, fermer }: Props) {
  const photo = photos[index];
  const aPrecedent = index > 0;
  const aSuivant = index >= 0 && index < photos.length - 1;
  const boutonFermer = useRef<HTMLButtonElement>(null);
  const dialogue = useRef<HTMLDivElement>(null);
  const fond = useRef<HTMLDivElement>(null);
  const mouvementReduit = useMouvementReduit();
  const [present, retirer] = usePresence();
  // « Réduire les animations » : une photo animée reste fixe ; le bouton
  // « Animer » la joue une fois (chaque clic remonte le composant, donc rejoue).
  // Le compteur est lié à la photo : on repart de zéro en changeant de photo.
  const [animations, setAnimations] = useState({ id: -1, n: 0 });
  const nbAnimations = animations.id === photo?.id ? animations.n : 0;

  // Sens du dernier changement de photo (glissement), dérivé pendant le rendu.
  const [suivi, setSuivi] = useState<{ index: number; sens: Sens }>({ index, sens: 1 });
  if (suivi.index !== index) setSuivi({ index, sens: index > suivi.index ? 1 : -1 });
  const sens = suivi.index !== index ? (index > suivi.index ? 1 : -1) : suivi.sens;

  // Pendant la fermeture, plus aucune commande (un second Échap fermerait la page jour).
  const actif = present;
  useTouchesClavier({
    Escape: () => actif && fermer(),
    ArrowLeft: () => actif && aPrecedent && precedent(),
    ArrowRight: () => actif && aSuivant && suivant(),
  });

  const glissement = useGlissement((d) => {
    if (!actif) return;
    if (d === "suivant" && aSuivant) suivant();
    if (d === "precedent" && aPrecedent) precedent();
  });

  // --- Ouverture ---------------------------------------------------------------
  const ouvertureAnimee = depuisGalerie;
  useVolEntrant(
    photo ? idPhoto(photo.id) : "",
    () => (photo ? dialogue.current?.querySelector<HTMLElement>(selecteurTransition(idPhoto(photo.id))) ?? null : null),
    () => (ouvertureAnimee && !mouvementReduit ? { transition: volPhoto(1) } : null),
  );
  useLayoutEffect(() => {
    if (!ouvertureAnimee || !dialogue.current || !fond.current) return;
    // Le fond noir et les commandes apparaissent pendant que la photo grandit ;
    // en mouvement réduit, toute la visionneuse apparaît en fondu.
    const cibles = mouvementReduit ? [dialogue.current] : [fond.current, ...dialogue.current.querySelectorAll("[data-chrome]")];
    const controle = animate(cibles, { opacity: [0, 1] }, transitionFondVisionneuse(1, mouvementReduit));
    return () => controle.stop();
    // Au montage seulement.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Fermeture ---------------------------------------------------------------
  useLayoutEffect(() => {
    if (present) return;
    const racine = dialogue.current;
    if (!racine) return retirer();
    racine.style.pointerEvents = "none";
    // Geste « retour » d'iOS déjà animé par le navigateur : on n'en rajoute pas.
    if (consommerRetourDejaAnime()) return retirer();

    const id = photo ? idPhoto(photo.id) : null;
    const source = id ? racine.querySelector<HTMLElement>(selecteurTransition(id)) : null;
    const arrivee = id ? miniature(id, racine) : null;
    // La miniature de la dernière photo vue est ramenée à l'écran AVANT d'y voler.
    arrivee?.scrollIntoView({ block: "nearest" });

    if (mouvementReduit || !source || !arrivee) {
      animate(racine, { opacity: 0 }, mouvementReduit ? fondu() : transitionFondVisionneuse(-1, false)).then(retirer);
      return;
    }
    animate([fond.current!, ...racine.querySelectorAll("[data-chrome]")], { opacity: 0 }, transitionFondVisionneuse(-1, false));
    lancerVol({ source, cible: arrivee, transition: volPhoto(-1), atterri: retirer });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [present]);

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
      <div ref={fond} className={styles.fond} aria-hidden />

      <div className={styles.barre} data-chrome>
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
        <AnimatePresence initial={false} custom={sens}>
          <motion.div
            key={photo?.id ?? "introuvable"}
            className={styles.diapo}
            custom={sens}
            variants={variantesPhotoVoisine(mouvementReduit)}
            initial="initial"
            animate="visible"
            exit="sortie"
          >
              {photo?.type === "video" ? (
                <LecteurVideo photo={photo} alt={alt} transitionId={idPhoto(photo.id)} />
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
                <Photo photo={photo} mode="contenir" sizes="100vw" priorite alt={alt} transitionId={idPhoto(photo.id)} />
              ) : (
                <p className={styles.introuvable}>Cette photo n’existe pas dans ce jour.</p>
              )}
          </motion.div>
        </AnimatePresence>
        <div className={styles.fleches} data-chrome>
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
      </div>

      <div className={styles.legende} data-chrome>
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
