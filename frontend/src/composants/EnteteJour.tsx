import { Link } from "react-router";
import type { JourDetail } from "../api/types";
import { chemins } from "../lib/chemins";
import { dateLongue, pluriel } from "../lib/dates";
import styles from "./EnteteJour.module.css";

export default function EnteteJour({ jour }: { jour: JourDetail }) {
  return (
    <header className={styles.entete}>
      <Link to={chemins.voyage(jour.voyage.slug)} className={styles.retour}>
        <span aria-hidden>←</span> {jour.voyage.titre}
      </Link>
      <p className={styles.date}>{dateLongue(jour.date)}</p>
      <h1 className={styles.titre}>{jour.titre || "Sans titre"}</h1>
      <p className={styles.meta}>
        {[jour.lieu, pluriel(jour.photos.length, "photo")].filter(Boolean).join(" · ")}
      </p>
    </header>
  );
}
