import { useRef, type RefObject } from "react";
import { useAuDefilement } from "../hooks/useAuDefilement";
import { libelleHeure } from "../lib/dates";
import styles from "./GaleriePhotos.module.css";

/**
 * Filet de progression de la journée : se remplit (scaleX) du haut de la
 * galerie (elle touche le haut de l'écran) à sa fin (elle touche le bas).
 * Chaque intitulé a le sien, tous suivent le même défilement : seul celui qui
 * colle est visible.
 */
export default function ProgressionJour({ racine, fin }: { racine: RefObject<HTMLElement | null>; fin: number }) {
  const rempli = useRef<HTMLSpanElement>(null);
  useAuDefilement(rempli, racine, { transform: ["scaleX(0)", "scaleX(1)"] }, ["start start", "end end"]);
  return (
    <>
      <span className={styles.filet} aria-hidden="true">
        <span ref={rempli} className={styles.rempli} />
      </span>
      <span className={styles.fin} aria-hidden="true">
        {libelleHeure(fin)}
      </span>
    </>
  );
}

