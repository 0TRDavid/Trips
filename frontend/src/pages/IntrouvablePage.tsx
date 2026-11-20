import { Link } from "react-router";
import styles from "./IntrouvablePage.module.css";

/** Page 404, rendue dans le cadre du site. `erreur` : plantage inattendu. */
export default function IntrouvablePage({ erreur = false }: { erreur?: boolean }) {
  return (
    <section className={styles.page}>
      <p className={styles.code}>{erreur ? "Oups" : "404"}</p>
      <h1>{erreur ? "Quelque chose s’est mal passé" : "Cette page n’existe pas"}</h1>
      <p className={styles.texte}>
        {erreur
          ? "Recharge la page ; si le problème persiste, regarde la console du navigateur."
          : "Le voyage, le jour ou la photo demandés sont introuvables."}
      </p>
      <Link to="/" className={styles.lien} reloadDocument={erreur}>
        Revenir aux voyages
      </Link>
    </section>
  );
}
