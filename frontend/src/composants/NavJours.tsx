import { useEffect } from "react";
import { Link } from "react-router";
import { prechargerJour } from "../api/requetes";
import type { JourVoisin } from "../api/types";
import { chemins } from "../lib/chemins";
import { dateCourte } from "../lib/dates";
import Photo from "./Photo";
import styles from "./NavJours.module.css";

type Props = { slug: string; precedent: JourVoisin | null; suivant: JourVoisin | null };

/** Jour précédent / suivant. Les deux voisins sont préchargés : clic instantané. */
export default function NavJours({ slug, precedent, suivant }: Props) {
  useEffect(() => {
    if (precedent) void prechargerJour(slug, precedent.date);
    if (suivant) void prechargerJour(slug, suivant.date);
  }, [slug, precedent, suivant]);

  return (
    <nav className={styles.nav} aria-label="Jours voisins">
      {precedent ? <Voisin slug={slug} jour={precedent} sens="precedent" /> : <span />}
      {suivant ? <Voisin slug={slug} jour={suivant} sens="suivant" /> : <span />}
    </nav>
  );
}

function Voisin({ slug, jour, sens }: { slug: string; jour: JourVoisin; sens: "precedent" | "suivant" }) {
  return (
    <Link
      to={chemins.jour(slug, jour.date)}
      className={styles.voisin}
      data-sens={sens}
      rel={sens === "precedent" ? "prev" : "next"}
    >
      <span className={styles.vignette}>
        {jour.photo && <Photo photo={jour.photo} mode="couvrir" sizes="80px" alt="" />}
      </span>
      <span className={styles.texte}>
        <span className={styles.sens}>
          {sens === "precedent" ? "← Jour précédent" : "Jour suivant →"}
        </span>
        <span className={styles.titre}>{jour.titre || dateCourte(jour.date)}</span>
        {jour.titre && <span className={styles.date}>{dateCourte(jour.date)}</span>}
      </span>
    </Link>
  );
}
