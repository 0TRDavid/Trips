import { useMemo, useRef, type CSSProperties } from "react";
import { Link } from "react-router";
import type { BlocRecit, PhotoJour } from "../api/types";
import { useApparitionPhotos } from "../hooks/useApparitionPhotos";
import { ContexteLecture, useNouveauChefDeLecture } from "../hooks/useLecture";
import { chemins } from "../lib/chemins";
import { dateCourte, heureLocale, libelleHeure } from "../lib/dates";
import { reglages, type VarianteCollant } from "../lib/mouvement";
import { bornesHeures, entremeler } from "../lib/recit";
import { ratio } from "../lib/rendus";
import { idPhoto } from "../lib/transitions";
import { aUneVideo, formatDuree } from "../lib/videos";
import BandeauHeure from "./BandeauHeure";
import Photo from "./Photo";
import PhotoAnimee from "./PhotoAnimee";
import ProgressionJour from "./ProgressionJour";
import Recit from "./Recit";
import styles from "./GaleriePhotos.module.css";

type Props = {
  slug: string;
  date: string;
  photos: PhotoJour[];
  /** Récit découpé aux marqueurs `[[14h]]` (API : recit_blocs). */
  blocs: BlocRecit[];
  /** Visionneuse ouverte : les photos animées de la page se taisent. */
  suspendu: boolean;
};

/**
 * La journée, racontée au fil du défilement : photos regroupées par heure
 * (« 10 h », « 14 h »…), récit intercalé là où l'auteur l'a placé
 * (lib/recit.ts), intitulé d'heure collant avec la progression de la journée.
 *
 * Galerie en rangées justifiées, en CSS pur : chaque photo s'étire en
 * proportion de son ratio (flex-grow = largeur / hauteur), donc toutes les
 * photos d'une rangée ont la même hauteur et aucune n'est rognée. Les
 * dimensions viennent de l'API : la mise en page est juste avant le
 * chargement des images. L'ordre est celui de l'API (heure de prise, sauf
 * retouche dans l'admin).
 *
 * Vie de la page, toujours jouée par le navigateur :
 * - photos et blocs du récit apparaissent une fois à leur entrée dans l'écran
 *   (hooks/useApparitionPhotos.ts) ;
 * - une seule photo animée joue, la plus proche du centre (lib/lecture.ts) ;
 * - le filet de l'intitulé collant se remplit avec le défilement.
 */
export default function GaleriePhotos({ slug, date, photos, blocs, suspendu }: Props) {
  const racine = useRef<HTMLDivElement>(null);
  const elements = useMemo(() => entremeler(photos, blocs), [photos, blocs]);
  const bornes = useMemo(() => bornesHeures(photos), [photos]);
  const collant: VarianteCollant = reglages().collant;
  const chef = useNouveauChefDeLecture(suspendu);
  useApparitionPhotos(racine, true);
  let numero = 0;

  return (
    <ContexteLecture.Provider value={chef}>
      <div ref={racine} className={styles.journee} data-collant={collant}>
        {collant === "bandeau" && bornes && <BandeauHeure racine={racine} bornes={bornes} />}
        {elements.map((element, i) => {
          if (element.genre === "recit") {
            return <BlocDuRecit key={`r${i}`} html={element.html} />;
          }
          const idTitre = `moment-${numero++}`;
          // Largeur « naturelle » du moment, en hauteurs de rangée (somme des
          // ratios) : un moment court (sans récit au milieu) tient sur une
          // seule rangée sur ordinateur et partage sa ligne (GaleriePhotos.module.css).
          const somme = element.segments.reduce(
            (total, s) => (s.genre === "photos" ? total + s.photos.reduce((t, p) => t + ratio(p), 0) : total),
            0,
          );
          const court = somme <= SOMME_COURT && element.segments.length === 1;
          return (
            <section
              key={`m${i}-${element.heure}`}
              className={styles.moment}
              aria-labelledby={idTitre}
              data-heure={element.heure ?? ""}
              data-court={court ? "" : undefined}
              style={{ "--somme": somme } as CSSProperties}
            >
              <h2 id={idTitre} className={styles.heure}>
                <span className={styles.libelle}>{libelleHeure(element.heure)}</span>
                {collant === "pousse" && bornes && <ProgressionJour racine={racine} fin={bornes[1]} />}
              </h2>
              {element.segments.map((segment, j) =>
                segment.genre === "recit" ? (
                  <BlocDuRecit key={`r${j}`} html={segment.html} />
                ) : (
                  <Rangees key={`p${j}`} slug={slug} date={date} photos={segment.photos} />
                ),
              )}
            </section>
          );
        })}
      </div>
    </ContexteLecture.Provider>
  );
}

/** Un moment « court » est ramené sur une rangée : jusqu'à 4 paysages 3:2 ou 6 portraits. */
const SOMME_COURT = 6;

function BlocDuRecit({ html }: { html: string }) {
  return (
    <div className={styles.recit} data-apparition="">
      <Recit html={html} />
    </div>
  );
}

type PropsRangees = { slug: string; date: string; photos: PhotoJour[] };

function Rangees({ slug, date, photos }: PropsRangees) {
  return (
    <ul className={styles.galerie}>
      {photos.map((photo) => {
        const r = ratio(photo);
        // Largeur affichée ≈ ratio × hauteur de rangée (avec marge pour l'étirement).
        const sizes = `(min-width: 1700px) ${Math.round(r * 400 * 1.5)}px, (min-width: 1200px) ${Math.round(r * 320 * 1.5)}px, (min-width: 700px) ${Math.round(r * 260 * 1.5)}px, min(100vw, ${Math.round(r * 110 * 2)}px)`;
        const nature = photo.type === "video" ? "Vidéo" : "Photo";
        const alt = photo.legende || `${nature} du ${dateCourte(date)}${photo.prise_le ? ` à ${heureLocale(photo.prise_le)}` : ""}`;
        const image =
          photo.type === "animee" && aUneVideo(photo) ? (
            <PhotoAnimee photo={photo} sizes={sizes} alt={alt} transitionId={idPhoto(photo.id)} />
          ) : (
            <Photo photo={photo} sizes={sizes} alt={alt} transitionId={idPhoto(photo.id)} />
          );
        return (
          <li key={photo.id} className={styles.cellule} style={{ "--ratio": r } as CSSProperties} data-apparition="">
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
