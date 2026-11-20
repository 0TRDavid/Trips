import { useState } from "react";
import type { CSSProperties } from "react";
import type { PhotoResume } from "../api/types";
import { placeholderDataUrl } from "../lib/placeholder";
import { ratio, srcParDefaut, srcset } from "../lib/rendus";
import styles from "./Photo.module.css";

type Props = {
  photo: PhotoResume;
  /**
   * Largeur d'affichage, pour que le navigateur choisisse le bon rendu dans
   * le srcset. Ex. "(min-width: 900px) 33vw, 50vw".
   */
  sizes: string;
  /**
   * - "naturel" (défaut) : la boîte prend le ratio de la photo, sa largeur
   *   vient du parent ;
   * - "couvrir" : remplit le parent (qui fixe la taille), quitte à rogner ;
   * - "contenir" : la plus grande taille possible dans le parent sans rogner
   *   (visionneuse). La boîte colle à la photo : son fond flou ne déborde pas.
   */
  mode?: "naturel" | "couvrir" | "contenir";
  /** Image importante, visible tout de suite (couverture, visionneuse). */
  priorite?: boolean;
  alt: string;
  /** Identifiant partagé avec l'élément d'une autre page (étape 6). */
  transitionId?: string;
  className?: string;
};

/**
 * LE composant d'affichage des photos du site.
 *
 * Sans attendre l'image :
 * 1. la place est réservée aux dimensions exactes (aspect-ratio) : rien ne
 *    bouge quand l'image arrive ;
 * 2. on affiche la couleur dominante, puis par-dessus le ThumbHash (image floue
 *    de ~30 px décodée localement) ;
 * 3. l'image (srcset) apparaît quand elle est chargée et décodée.
 */
export default function Photo({
  photo,
  sizes,
  mode = "naturel",
  priorite = false,
  alt,
  transitionId,
  className,
}: Props) {
  const src = srcParDefaut(photo);
  // On mémorise QUELLE image est chargée (et non un simple booléen) : si la
  // photo change, l'état repart de zéro sans effet à écrire.
  const [chargee, setChargee] = useState<string | undefined>();
  const estChargee = chargee !== undefined && chargee === src;
  const flou = placeholderDataUrl(photo.placeholder);
  const r = ratio(photo);

  const cadre = (
    <div
      className={[styles.cadre, styles[mode], className].filter(Boolean).join(" ")}
      style={
        {
          "--ratio": r,
          backgroundColor: photo.couleur || undefined,
          backgroundImage: flou ? `url(${flou})` : undefined,
        } as CSSProperties
      }
      data-transition-id={transitionId}
    >
      {src && (
        <img
          // Image déjà en cache : `complete` est vrai avant même onLoad.
          ref={(img) => {
            if (img?.complete && img.naturalWidth > 0) setChargee(img.getAttribute("src") ?? undefined);
          }}
          className={styles.image}
          src={src}
          srcSet={srcset(photo)}
          sizes={sizes}
          width={photo.largeur || undefined}
          height={photo.hauteur || undefined}
          alt={alt}
          loading={priorite ? "eager" : "lazy"}
          fetchPriority={priorite ? "high" : "auto"}
          decoding="async"
          draggable={false}
          data-chargee={estChargee || undefined}
          onLoad={() => setChargee(src)}
        />
      )}
    </div>
  );

  // « contenir » a besoin d'un conteneur de requête (cqw/cqh) pour calculer
  // la plus grande boîte au bon ratio qui tient dans le parent.
  return mode === "contenir" ? <div className={styles.zone}>{cadre}</div> : cadre;
}
