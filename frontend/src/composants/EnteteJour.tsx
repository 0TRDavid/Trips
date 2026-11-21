import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { Link } from "react-router";
import type { JourDetail } from "../api/types";
import { useAuDefilement } from "../hooks/useAuDefilement";
import { EVENEMENT_RECIT } from "../hooks/useDefilementParPage";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { useVolEntrant } from "../hooks/useVolEntrant";
import { useApresVol, useNavigationPage } from "../layout/contexte";
import { chemins } from "../lib/chemins";
import { dateLongue, pluriel } from "../lib/dates";
import {
  arriveeTitre,
  courseOuverture,
  defilement,
  ouverturePleinEcran,
  rebondIndice,
  recitCouverture,
  volEnTete,
  type MesuresPlein,
} from "../lib/mouvement";
import { estClaire } from "../lib/palette";
import { idJour } from "../lib/transitions";
import BarreJour from "./BarreJour";
import Photo from "./Photo";
import Recit from "./Recit";
import styles from "./EnteteJour.module.css";

/**
 * Ouverture d'un jour (premier favori du jour, sinon sa première photo, comme
 * la vignette de la timeline). En venant de la page du voyage, la vignette du
 * jour « vole » jusqu'ici et devient la couverture ; au retour, elle regagne
 * la timeline.
 *
 * La photo occupe d'abord tout l'écran, la date et le titre posés dessus
 * (arrivés de la gauche ; clairs sur voile sombre, ou sombres sur voile clair
 * si la photo est claire). Au défilement, elle rétrécit jusqu'au bandeau et le
 * titre se retrouve dessous, sur le fond de la page. Dans la page, le cadre
 * garde la hauteur du bandeau : il est seulement étiré à l'écran (transform),
 * et le titre, déjà à sa place sous le bandeau, est donc d'abord sur la photo.
 * Quand le titre va sortir de l'écran, la barre du jour prend le relais
 * (BarreJour). Mouvement réduit : bandeau fixe, titre dessous, fondus.
 *
 * Ouverture vraiment plein écran : pas de marque du site par-dessus (classe
 * `sans-marque` sur <html> tant que la page est là) ; le retour vers le voyage
 * est dans la barre du jour, et en tête de page pour le clavier seulement.
 * En bas au centre, « Glisser » et une flèche qui rebondit, effacés dès qu'on
 * défile.
 *
 * Galerie plein écran (`recit`) : le début du récit du jour est posé à droite
 * de la couverture, révélé au premier cran de molette (useDefilementParPage),
 * puis effacé au défilement avec la couverture.
 */
export default function EnteteJour({ jour, recit }: { jour: JourDetail; recit?: string }) {
  const visuel = useRef<HTMLDivElement>(null);
  const reduit = useMouvementReduit();
  const couverture = jour.photos.find((p) => p.favori) ?? jour.photos[0];
  const plein = !reduit && !!couverture;
  const ouverture = useOuverturePleinEcran(plein, visuel);
  const nav = useNavigationPage();
  const id = idJour(jour.voyage.slug, jour.date);
  useVolEntrant(
    id,
    () => ouverture.cadre.current,
    () => (nav.genre === "ouvrirJour" && nav.sens === 1 ? { transition: volEnTete(1) } : null),
  );

  useEffect(() => {
    document.documentElement.classList.add("sans-marque");
    return () => document.documentElement.classList.remove("sans-marque");
  }, []);

  const titre = jour.titre || "Sans titre";
  const meta = [jour.lieu, pluriel(jour.photos.length, "photo")].filter(Boolean).join(" · ");
  const m = ouverture.mesures;
  return (
    <header
      className={styles.entete}
      style={couverture ? ({ "--couleur-photo": couverture.couleur } as CSSProperties) : undefined}
      data-clair={couverture && estClaire(couverture.couleur) ? "" : undefined}
      data-plein={plein ? "" : undefined}
    >
      <Retour jour={jour} />
      {couverture && (
        <>
          <div ref={visuel} className={`${styles.visuel} ${styles.visuelPlein}`}>
            {/* Piste du défilement : de la page tout en haut à la fin de l'ouverture. */}
            <div
              ref={ouverture.piste}
              className={styles.piste}
              style={m ? { top: -m.haut, height: m.course } : undefined}
              aria-hidden
            />
            <div ref={ouverture.cadre} className={styles.cadrePlein} data-transition-id={id}>
              <div ref={ouverture.photo} className={styles.photoPlein} style={m ? { height: m.plein } : undefined}>
                <Photo photo={couverture} mode="couvrir" sizes="100vw" priorite alt="" />
              </div>
              <div ref={ouverture.voile} className={styles.voile} aria-hidden />
            </div>
            {m && recit && <RecitCouverture html={recit} hauteur={m.plein} enveloppe={ouverture.recit} />}
            {m && (
              <div
                ref={ouverture.indice}
                className={styles.indice}
                style={{ top: m.plein - defilement.plein.margeTitre, height: defilement.plein.margeTitre }}
                aria-hidden
              >
                <span ref={ouverture.fleche} className={styles.indiceContenu}>
                  Glisser
                  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </span>
              </div>
            )}
          </div>
          <div className={styles.filet} aria-hidden />
        </>
      )}
      <div ref={ouverture.titres} className={styles.titres} data-attente={ouverture.apresVol ? undefined : ""}>
        <div ref={ouverture.titre} className={styles.titresNormaux}>
          <p className={styles.date}>{dateLongue(jour.date)}</p>
          <h1 className={styles.titre}>{titre}</h1>
          <p className={styles.meta}>{meta}</p>
        </div>
        <div ref={ouverture.titreSurPhoto} className={styles.titresSurPhoto} aria-hidden>
          <p className={styles.date}>{dateLongue(jour.date)}</p>
          <p className={styles.titre}>{titre}</p>
          <p className={styles.meta}>{meta}</p>
        </div>
      </div>
      {couverture && <BarreJour jour={jour} couverture={couverture} titres={ouverture.titres} />}
    </header>
  );
}

function Retour({ jour, className }: { jour: JourDetail; className?: string }) {
  return (
    <Link to={chemins.voyage(jour.voyage.slug)} className={className ?? styles.retour}>
      <span aria-hidden>←</span> {jour.voyage.titre}
    </Link>
  );
}

/** Récit posé à droite de la couverture (caché jusqu'au premier cran). */
function RecitCouverture({
  html,
  hauteur,
  enveloppe,
}: {
  html: string;
  hauteur: number;
  enveloppe: RefObject<HTMLDivElement | null>;
}) {
  const panneau = useRef<HTMLDivElement>(null);
  const [montre, setMontre] = useState(false);
  const reduit = useMouvementReduit();
  const premier = useRef(true);

  useEffect(() => {
    const ecouter = (e: Event) => setMontre((e as CustomEvent<boolean>).detail);
    window.addEventListener(EVENEMENT_RECIT, ecouter);
    return () => window.removeEventListener(EVENEMENT_RECIT, ecouter);
  }, []);

  useLayoutEffect(() => {
    const el = panneau.current;
    if (!el) return;
    if (premier.current) {
      premier.current = false;
      return;
    }
    const a = recitCouverture(montre, reduit);
    const fin = a.images[a.images.length - 1];
    el.style.opacity = String(fin.opacity);
    el.style.transform = String(fin.transform ?? "none");
    el.animate(a.images, a.options);
  }, [montre, reduit]);

  return (
    <div ref={enveloppe} className={styles.recitCouverture} style={{ height: hauteur }}>
      <div
        ref={panneau}
        className={styles.recitPanneau}
        data-recit-couverture=""
        data-montre={montre ? "" : undefined}
      >
        <div className={styles.recitDefile} data-defile="">
          <Recit html={html} className={styles.recitTexte} />
        </div>
      </div>
    </div>
  );
}

type Mesures = MesuresPlein & { course: number };

/**
 * Mesures et animations de l'ouverture plein écran. Les transforms de départ
 * sont posés avant la première peinture (le vol d'arrivée mesure le cadre déjà
 * étiré) ; ensuite, Motion `scroll()` les joue au défilement.
 */
function useOuverturePleinEcran(actif: boolean, visuel: RefObject<HTMLDivElement | null>) {
  const piste = useRef<HTMLDivElement>(null);
  const cadre = useRef<HTMLDivElement>(null);
  const photo = useRef<HTMLDivElement>(null);
  const voile = useRef<HTMLDivElement>(null);
  const titres = useRef<HTMLDivElement>(null);
  const titre = useRef<HTMLDivElement>(null);
  const titreSurPhoto = useRef<HTMLDivElement>(null);
  const indice = useRef<HTMLDivElement>(null);
  const fleche = useRef<HTMLSpanElement>(null);
  const recit = useRef<HTMLDivElement>(null);
  const [mesures, setMesures] = useState<Mesures | null>(null);
  const reduit = useMouvementReduit();
  const apresVol = useApresVol();

  useLayoutEffect(() => {
    if (!actif) return;
    let largeur = 0;
    let hauteur = 0;
    const mesurer = () => {
      const el = visuel.current;
      if (!el) return;
      // Hauteur seule qui bouge un peu (barre d'adresse d'un téléphone) : on garde.
      if (window.innerWidth === largeur && Math.abs(window.innerHeight - hauteur) < 120) return;
      largeur = window.innerWidth;
      hauteur = window.innerHeight;
      const haut = el.getBoundingClientRect().top + window.scrollY;
      const bandeau = el.offsetHeight;
      const plein = Math.max(hauteur - haut, bandeau);
      // Bas du titre à sa place, sous le bandeau : l'enveloppe ne porte pas les
      // translations liées au défilement (posées sur ses deux enfants).
      const r = titres.current?.getBoundingClientRect();
      const basTitre = r ? r.bottom + window.scrollY : haut + bandeau;
      const base = { haut, bandeau, plein, basTitre };
      const m = { ...base, course: courseOuverture(base, hauteur) };
      const depart = ouverturePleinEcran(m);
      cadre.current?.style.setProperty("transform", depart.cadre.transform[0]);
      photo.current?.style.setProperty("transform", depart.photo.transform[0]);
      titre.current?.style.setProperty("transform", depart.titre.transform[0]);
      titreSurPhoto.current?.style.setProperty("transform", depart.titreSurPhoto.transform[0]);
      setMesures(m);
    };
    mesurer();
    window.addEventListener("resize", mesurer);
    return () => window.removeEventListener("resize", mesurer);
  }, [actif, visuel]);

  const o = mesures ? ouverturePleinEcran(mesures) : null;
  const plage: ["start start", "end start"] = ["start start", "end start"];
  useAuDefilement(cadre, piste, o?.cadre ?? null, plage);
  useAuDefilement(photo, piste, o?.photo ?? null, plage);
  useAuDefilement(voile, piste, o?.voile ?? null, plage);
  useAuDefilement(titre, piste, o?.titre ?? null, plage);
  useAuDefilement(titreSurPhoto, piste, o?.titreSurPhoto ?? null, plage);
  useAuDefilement(indice, piste, o?.indice ?? null, plage);
  useAuDefilement(recit, piste, o?.recit ?? null, plage);

  // La flèche rebondit en boucle (rien en mouvement réduit).
  const avecIndice = !!mesures;
  useEffect(() => {
    const a = rebondIndice(reduit);
    if (!avecIndice || !a || !fleche.current) return;
    const animation = fleche.current.animate(a.images, a.options);
    return () => animation.cancel();
  }, [avecIndice, reduit]);

  // Le titre arrive de la gauche, une fois, quand la photo a fini de voler
  // (avant la peinture : il reste caché jusque-là, data-attente).
  useLayoutEffect(() => {
    if (!actif || !apresVol) return;
    const a = arriveeTitre(reduit);
    titres.current?.animate(a.images, a.options);
  }, [actif, apresVol, reduit]);

  return { piste, cadre, photo, voile, titres, titre, titreSurPhoto, indice, fleche, recit, mesures, apresVol };
}
