import type { CSSProperties } from "react";
import { Link } from "react-router";
import type { PhotoJour } from "../api/types";
import { chemins } from "../lib/chemins";
import { dateCourte, heureLocale, libelleHeure, momentsParHeure } from "../lib/dates";
import { ratio } from "../lib/rendus";
import { idPhoto } from "../lib/transitions";
import { aUneVideo, formatDuree } from "../lib/videos";
import Photo from "./Photo";
import PhotoAnimee from "./PhotoAnimee";
import styles from "./GaleriePhotos.module.css";

type Props = { slug: string; date: string; photos: PhotoJour[] };

/**
 * Galerie en rangées justifiées, en CSS pur : chaque photo s'étire en
 * proportion de son ratio (flex-grow = largeur / hauteur), donc toutes les
 * photos d'une rangée ont la même hauteur et aucune n'est rognée. Les
 * dimensions viennent de l'API : la mise en page est juste avant le
 * chargement des images.
 *
 * Les photos sont regroupées par heure (« 10 h », « 14 h »…) pour suivre la
 * journée : chaque moment a son intitulé et ses propres rangées. L'ordre est
 * celui de l'API (heure de prise, sauf retouche dans l'admin).
 */
export default function GaleriePhotos({ slug, date, photos }: Props) {
  return (
    <div className={styles.moments}>
      {momentsParHeure(photos).map((moment, i) => {
        const idTitre = `moment-${i}`;
        return (
          <section key={`${i}-${moment.heure}`} className={styles.moment} aria-labelledby={idTitre}>
            <h2 id={idTitre} className={styles.heure}>
              {libelleHeure(moment.heure)}
            </h2>
            <Rangees slug={slug} date={date} photos={moment.photos} />
          </section>
        );
      })}
    </div>
  );
}

function Rangees({ slug, date, photos }: Props) {
  return (
    <ul className={styles.galerie}>
      {photos.map((photo) => {
        const r = ratio(photo);
        // Largeur affichée ≈ ratio × hauteur de rangée (avec marge pour l'étirement).
        const sizes = `(min-width: 1200px) ${Math.round(r * 320 * 1.5)}px, (min-width: 700px) ${Math.round(r * 260 * 1.5)}px, min(100vw, ${Math.round(r * 110 * 2)}px)`;
        const nature = photo.type === "video" ? "Vidéo" : "Photo";
        const alt = photo.legende || `${nature} du ${dateCourte(date)}${photo.prise_le ? ` à ${heureLocale(photo.prise_le)}` : ""}`;
        const image =
          photo.type === "animee" && aUneVideo(photo) ? (
            <PhotoAnimee photo={photo} sizes={sizes} alt={alt} transitionId={idPhoto(photo.id)} />
          ) : (
            <Photo photo={photo} sizes={sizes} alt={alt} transitionId={idPhoto(photo.id)} />
          );
        return (
          <li key={photo.id} className={styles.cellule} style={{ "--ratio": r } as CSSProperties}>
            <Link
              to={chemins.photo(slug, date, photo.id)}
              // La page jour reste en place derrière la visionneuse.
              preventScrollReset
              state={{ depuisJour: true }}
              className={styles.lien}
            >
              {image}
              {photo.type === "video" && (
                <span className={styles.badgeVideo} aria-hidden="true">
                  <span className={styles.triangle}>▶</span>
                  {formatDuree(photo.duree)}
                </span>
              )}
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
