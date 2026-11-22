import { useEffect, useMemo, useRef, useState, type CSSProperties, type RefObject } from "react";
import { useNavigate } from "react-router";
import type { BlocRecit, PhotoJour } from "../api/types";
import { useApparitionPhotos } from "../hooks/useApparitionPhotos";
import { useDefilementParPage } from "../hooks/useDefilementParPage";
import { ContexteLecture, useNouveauChefDeLecture } from "../hooks/useLecture";
import { chemins } from "../lib/chemins";
import { dateCourte, heureLocale, libelleHeure } from "../lib/dates";
import { reglages, type VarianteCollant } from "../lib/mouvement";
import { galeriePleinEcran, mosaiquePleinEcran } from "../lib/rangees";
import { bornesHeures, entremeler } from "../lib/recit";
import { estClaire } from "../lib/palette";
import { placeholderDataUrl } from "../lib/placeholder";
import { ratio } from "../lib/rendus";
import { idPhoto } from "../lib/transitions";
import { aUneVideo, formatDuree } from "../lib/videos";
import BandeauHeure from "./BandeauHeure";
import FriseHeures from "./FriseHeures";
import Photo from "./Photo";
import PhotoAnimee from "./PhotoAnimee";
import ProgressionJour from "./ProgressionJour";
import VideoGalerie from "./VideoGalerie";
import Recit from "./Recit";
import styles from "./GaleriePhotos.module.css";

type Props = {
  slug: string;
  date: string;
  photos: PhotoJour[];
  /** Page du jour suivant : la molette y mène depuis la dernière page (plein écran). */
  suivant?: string;
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
export default function GaleriePhotos({ slug, date, photos, blocs, suspendu, suivant }: Props) {
  const racine = useRef<HTMLDivElement>(null);
  const elements = useMemo(() => entremeler(photos, blocs), [photos, blocs]);
  const heuresMoments = useMemo(
    () => elements.flatMap((e) => (e.genre === "moment" ? [e.heure] : [])),
    [elements],
  );
  const bornes = useMemo(() => bornesHeures(photos), [photos]);
  const collant: VarianteCollant = reglages().collant;
  // Ordinateur : mosaïque plein écran, page par page. Téléphone : rangées, défilement libre.
  const pleinEcran = galeriePleinEcran();
  const naviguer = useNavigate();
  const place = usePlacePleinEcran(racine, pleinEcran);
  const versSuivant = useMemo(() => (suivant ? () => naviguer(suivant) : undefined), [suivant, naviguer]);
  useDefilementParPage(racine, !!place, place?.haut ?? 0, versSuivant);
  const chef = useNouveauChefDeLecture(suspendu);
  useApparitionPhotos(racine, true);
  // Visionneuse ouverte : les vidéos lues sur place se mettent en pause.
  useEffect(() => {
    if (!suspendu) return;
    racine.current?.querySelectorAll<HTMLVideoElement>("video[data-video-galerie]").forEach((v) => v.pause());
  }, [suspendu]);
  let numero = 0;

  return (
    <ContexteLecture.Provider value={chef}>
      <div ref={racine} className={styles.journee} data-collant={collant} data-plein-ecran={pleinEcran ? "" : undefined}>
        {pleinEcran && <div className={styles.sonde} aria-hidden />}
        {place && <FriseHeures racine={racine} heures={heuresMoments} haut={place.haut} />}
        {collant === "bandeau" && bornes && <BandeauHeure racine={racine} bornes={bornes} />}
        {elements.map((element, i) => {
          if (element.genre === "recit") {
            return <BlocDuRecit key={`r${i}`} html={element.html} />;
          }
          const idTitre = `moment-${numero++}`;
          return (
            <section
              key={`m${i}-${element.heure}`}
              className={styles.moment}
              aria-labelledby={idTitre}
              data-heure={element.heure ?? ""}
            >
              <h2 id={idTitre} className={styles.heure}>
                <span className={styles.libelle}>{libelleHeure(element.heure)}</span>
                {collant === "pousse" && bornes && <ProgressionJour racine={racine} fin={bornes[1]} />}
              </h2>
              {element.segments.map((segment, j) =>
                segment.genre === "recit" ? (
                  <BlocDuRecit key={`r${j}`} html={segment.html} />
                ) : (
                  place ? (
                    <MosaiquePleinEcran key={`p${j}`} slug={slug} date={date} photos={segment.photos} place={place} />
                  ) : (
                    <Rangees key={`p${j}`} slug={slug} date={date} photos={segment.photos} />
                  )
                ),
              )}
            </section>
          );
        })}
      </div>
    </ContexteLecture.Provider>
  );
}

function BlocDuRecit({ html }: { html: string }) {
  return (
    <div className={styles.recit} data-apparition="" data-ancre="">
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
        const sizes = `(min-width: 1700px) ${Math.round(r * 400 * 1.5)}px, (min-width: 1200px) ${Math.round(r * 320 * 1.5)}px, (min-width: 700px) ${Math.round(r * 260 * 1.5)}px, min(100vw, ${Math.round(r * 150 * 2)}px)`;
        return (
          <Cellule key={photo.id} slug={slug} date={date} photo={photo} sizes={sizes} style={{ "--ratio": r } as CSSProperties} />
        );
      })}
    </ul>
  );
}

/** largeur : de la frise au bord droit de l'écran ; ecran : hauteur d'une page ; haut : barre du jour (px). */
type Place = { largeur: number; ecran: number; haut: number };

/**
 * Mosaïque plein écran (ordinateur, lib/rangees.ts) : un paysage seul par
 * écran (il le remplit, ou entier sur sa version floue), les portraits par
 * deux, côte à côte, bord à bord.
 */
function MosaiquePleinEcran({ slug, date, photos, place }: PropsRangees & { place: Place }) {
  const pages = useMemo(
    () => mosaiquePleinEcran(photos.map(ratio), place.largeur, place.ecran),
    [photos, place],
  );
  return (
    <div className={styles.pages}>
      {pages.map((page) => {
        const { debut, cases } = page;
        if (page.gabarit === "seule") {
          // Photo seule : remplit l'écran, ou entière sur sa version floue.
          const photo = photos[debut];
          const fond = page.couvrir ? null : placeholderDataUrl(photo.placeholder);
          return (
            <div
              key={debut}
              className={styles.pagePhoto}
              style={{ height: place.ecran }}
              data-ancre=""
              data-legendes={photo.legende ? "" : undefined}
              data-couleur={photo.couleur_vive ?? undefined}
            >
              {fond && <div className={styles.fondFlou} style={{ backgroundImage: `url(${fond})` }} aria-hidden />}
              <ul className={styles.listePhoto}>
                <Cellule
                  slug={slug}
                  date={date}
                  photo={photo}
                  sizes={page.couvrir ? `${place.largeur}px` : `${Math.round(ratio(photo) * place.ecran)}px`}
                  className={styles.cellulePhoto}
                  style={{}}
                  mode={page.couvrir ? "couvrir" : "contenir"}
                  avecLegende
                />
              </ul>
            </div>
          );
        }
        return (
          <ul
            key={debut}
            className={styles.mosaique}
            style={{ height: place.ecran }}
            data-ancre=""
            data-legendes={cases.some((_, k) => photos[debut + k].legende) ? "" : undefined}
            data-couleur={cases.map((_, k) => photos[debut + k].couleur_vive).find(Boolean) ?? undefined}
          >
            {cases.map((c, k) => {
              const photo = photos[debut + k];
              return (
                <Cellule
                  key={photo.id}
                  slug={slug}
                  date={date}
                  photo={photo}
                  sizes={`${Math.round(c.l * place.largeur)}px`}
                  className={styles.tuile}
                  style={{ left: `${c.x * 100}%`, top: `${c.y * 100}%`, width: `${c.l * 100}%`, height: `${c.h * 100}%` }}
                  mode="couvrir"
                  avecLegende
                />
              );
            })}
          </ul>
        );
      })}
    </div>
  );
}

/**
 * Place d'une page plein écran : hauteur de l'écran moins la barre du jour
 * (mesurée par la sonde ; l'intitulé d'heure, caché, ne compte pas), et
 * largeur de la frise des heures au bord droit de l'écran.
 */
function usePlacePleinEcran(racine: RefObject<HTMLDivElement | null>, actif: boolean): Place | null {
  const [place, setPlace] = useState<Place | null>(null);
  useEffect(() => {
    const el = racine.current;
    if (!actif || !el) return;
    const mesurer = () => {
      const haut = el.querySelector<HTMLElement>(`.${styles.sonde}`)?.offsetHeight ?? 0;
      const ecran = Math.max(window.innerHeight - haut, 200);
      // Les pages vont jusqu'au bord droit de l'écran ; à gauche, la frise.
      const gauche = el.getBoundingClientRect().left + (parseFloat(getComputedStyle(el).paddingLeft) || 0);
      const largeur = document.documentElement.clientWidth - gauche;
      setPlace((p) => (p && p.largeur === largeur && p.ecran === ecran && p.haut === haut ? p : { largeur, ecran, haut }));
    };
    mesurer();
    const observateur = new ResizeObserver(mesurer);
    observateur.observe(el);
    window.addEventListener("resize", mesurer);
    return () => {
      observateur.disconnect();
      window.removeEventListener("resize", mesurer);
    };
  }, [racine, actif]);
  return actif ? place : null;
}

type PropsCellule = {
  slug: string;
  date: string;
  photo: PhotoJour;
  sizes: string;
  style: CSSProperties;
  className?: string;
  /** Mode d'affichage de Photo ("naturel" par défaut ; plein écran : couvrir / contenir). */
  mode?: "naturel" | "couvrir" | "contenir";
  /** Mosaïque plein écran : la légende est posée à droite, révélée au premier cran (useDefilementParPage). */
  avecLegende?: boolean;
};

function Cellule({ slug, date, photo, sizes, style, className, mode, avecLegende }: PropsCellule) {
  const naviguer = useNavigate();
  // Vidéo : lue sur place au clic (petit côté de la case, pour choisir 720p / 1080p).
  const lisible = photo.type === "video" && aUneVideo(photo);
  const [lecture, setLecture] = useState<number | null>(null);
  const ouvrir = (cible: HTMLElement) => {
    if (lisible) {
      if (lecture === null) {
        const r = cible.getBoundingClientRect();
        setLecture(Math.min(r.width, r.height));
      }
      return;
    }
    // La page jour reste en place derrière la visionneuse.
    naviguer(chemins.photo(slug, date, photo.id), { preventScrollReset: true, state: { depuisJour: true } });
  };
  const nature = photo.type === "video" ? "Vidéo" : "Photo";
  const alt = photo.legende || `${nature} du ${dateCourte(date)}${photo.prise_le ? ` à ${heureLocale(photo.prise_le)}` : ""}`;
  const image =
    photo.type === "animee" && aUneVideo(photo) ? (
      <PhotoAnimee photo={photo} sizes={sizes} alt={alt} transitionId={idPhoto(photo.id)} mode={mode} />
    ) : (
      <Photo photo={photo} sizes={sizes} alt={alt} transitionId={idPhoto(photo.id)} mode={mode}>
        {lecture !== null && <VideoGalerie photo={photo} petitCote={lecture} />}
      </Photo>
    );
  const enLecture = lecture !== null;
  return (
    <li className={className ?? styles.cellule} style={style} data-apparition="">
      {/* Pas de <a href> : le navigateur afficherait l'adresse en bas à gauche au survol. */}
      <div
        role={enLecture ? undefined : lisible ? "button" : "link"}
        tabIndex={enLecture ? undefined : 0}
        aria-label={enLecture ? undefined : lisible ? `Lire la vidéo${photo.duree ? ` (${formatDuree(photo.duree)})` : ""}` : alt}
        className={styles.lien}
        data-lecture={enLecture ? "" : undefined}
        onClick={(e) => ouvrir(e.currentTarget)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.target === e.currentTarget) {
            e.preventDefault();
            ouvrir(e.currentTarget);
          }
        }}
      >
        {image}
        {photo.type === "video" && !enLecture && (
          // Étiquette « Lire » au centre, dans l'esprit de « Glisser » (clair ou sombre selon la photo).
          <span className={styles.lireVideo} data-clair={estClaire(photo.couleur) ? "" : undefined} aria-hidden="true">
            <span className={styles.lireRond}>
              <span className={styles.lireTriangle} />
            </span>
            <span className={styles.lireTexte}>
              <span className={styles.lireMot}>Lire{photo.duree != null && " · "}</span>
              {formatDuree(photo.duree)}
            </span>
          </span>
        )}
        {photo.favori && !enLecture && (
          <span className={styles.favori} title="Favori" aria-label="Favori">
            ★
          </span>
        )}
      </div>
      {avecLegende && photo.legende && (
        <div
          className={styles.legende}
          data-legende=""
          data-clair={estClaire(photo.couleur) ? "" : undefined}
          style={{ "--couleur-photo": photo.couleur } as CSSProperties}
          aria-hidden="true"
        >
          <p>{photo.legende}</p>
        </div>
      )}
    </li>
  );
}
