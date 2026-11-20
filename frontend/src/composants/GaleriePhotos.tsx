import type { CSSProperties } from "react";
import { Link } from "react-router";
import type { PhotoJour } from "../api/types";
import { chemins } from "../lib/chemins";
import { dateCourte, heureLocale } from "../lib/dates";
import { ratio } from "../lib/rendus";
import { idPhoto } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./GaleriePhotos.module.css";

type Props = { slug: string; date: string; photos: PhotoJour[] };

/**
 * Galerie en rangées justifiées, en CSS pur : chaque photo s'étire en
 * proportion de son ratio (flex-grow = largeur / hauteur), donc toutes les
 * photos d'une rangée ont la même hauteur et aucune n'est rognée. Les
 * dimensions viennent de l'API : la mise en page est juste avant le
 * chargement des images.
 */
export default function GaleriePhotos({ slug, date, photos }: Props) {
  return (
    <ul className={styles.galerie}>
      {photos.map((photo) => {
        const r = ratio(photo);
        // Largeur affichée ≈ ratio × hauteur de rangée (avec marge pour l'étirement).
        const sizes = `(min-width: 1200px) ${Math.round(r * 320 * 1.5)}px, (min-width: 700px) ${Math.round(r * 260 * 1.5)}px, min(100vw, ${Math.round(r * 110 * 2)}px)`;
        const alt = photo.legende || `Photo du ${dateCourte(date)}${photo.prise_le ? ` à ${heureLocale(photo.prise_le)}` : ""}`;
        return (
          <li key={photo.id} className={styles.cellule} style={{ "--ratio": r } as CSSProperties}>
            <Link
              to={chemins.photo(slug, date, photo.id)}
              // La page jour reste en place derrière la visionneuse.
              preventScrollReset
              state={{ depuisJour: true }}
              className={styles.lien}
            >
              <Photo photo={photo} sizes={sizes} alt={alt} transitionId={idPhoto(photo.id)} />
              {photo.favori && (
                <span className={styles.favori} title="Favori" aria-label="Favori">
                  ★
                </span>
              )}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
