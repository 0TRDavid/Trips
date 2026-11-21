import { useRef } from "react";
import { Link } from "react-router";
import type { JourDetail } from "../api/types";
import { useAuDefilement } from "../hooks/useAuDefilement";
import { useMouvementReduit } from "../hooks/useMouvementReduit";
import { useVolEntrant } from "../hooks/useVolEntrant";
import { useNavigationPage } from "../layout/contexte";
import { chemins } from "../lib/chemins";
import { dateLongue, pluriel } from "../lib/dates";
import { ouvertureAuDefilement, reglages, volEnTete } from "../lib/mouvement";
import { idJour } from "../lib/transitions";
import Photo from "./Photo";
import styles from "./EnteteJour.module.css";

/**
 * Ouverture d'un jour : grande photo (premier favori du jour, sinon sa
 * première photo, comme la vignette de la timeline), puis date, titre et lieu
 * (hors de la photo : contraste garanti). En venant de la page du voyage, la
 * vignette du jour « vole » jusqu'ici et devient la couverture ; au retour,
 * elle regagne la timeline.
 *
 * Au défilement, la photo glisse moins vite que la page et pâlit (lié au
 * défilement, joué par le navigateur : hooks/useAuDefilement.ts). On anime
 * un cadre intérieur, pas `visuel` : c'est lui que le vol mesure.
 */
export default function EnteteJour({ jour }: { jour: JourDetail }) {
  const visuel = useRef<HTMLDivElement>(null);
  const parallaxe = useRef<HTMLDivElement>(null);
  const reduit = useMouvementReduit();
  useAuDefilement(parallaxe, visuel, reduit ? null : ouvertureAuDefilement(reglages().ouverture), ["start start", "end start"]);
  const nav = useNavigationPage();
  const couverture = jour.photos.find((p) => p.favori) ?? jour.photos[0];
  const id = idJour(jour.voyage.slug, jour.date);
  useVolEntrant(
    id,
    () => visuel.current,
    () => (nav.genre === "ouvrirJour" && nav.sens === 1 ? { transition: volEnTete(1) } : null),
  );

  return (
    <header className={styles.entete}>
      <Link to={chemins.voyage(jour.voyage.slug)} className={styles.retour}>
        <span aria-hidden>←</span> {jour.voyage.titre}
      </Link>
      {couverture && (
        <>
          <div ref={visuel} className={styles.visuel} data-transition-id={id}>
            <div ref={parallaxe} className={styles.parallaxe}>
              <Photo photo={couverture} mode="couvrir" sizes="100vw" priorite alt="" />
            </div>
          </div>
          <div className={styles.filet} aria-hidden />
        </>
      )}
      <p className={styles.date}>{dateLongue(jour.date)}</p>
      <h1 className={styles.titre}>{jour.titre || "Sans titre"}</h1>
      <p className={styles.meta}>
        {[jour.lieu, pluriel(jour.photos.length, "photo")].filter(Boolean).join(" · ")}
      </p>
    </header>
  );
}
