import { Link, ScrollRestoration, useLocation, useOutlet } from "react-router";
import { clePage } from "../lib/chemins";
import styles from "./Layout.module.css";

/**
 * Cadre commun à toutes les pages, jamais démonté.
 *
 * Préparation de l'étape 6 : la page courante est récupérée avec useOutlet()
 * et identifiée par une clé (`clePage`). Pour animer l'entrée et la sortie
 * des pages, il suffira d'entourer ce bloc d'un <AnimatePresence> de Motion :
 * l'ancienne page restera affichée le temps de sa sortie.
 */
export default function Layout() {
  const page = useOutlet();
  const { pathname } = useLocation();

  return (
    <div className={styles.site}>
      <a className={styles.evitement} href="#contenu">
        Aller au contenu
      </a>
      <header className={styles.entete}>
        <Link to="/" className={styles.marque}>
          Carnet de voyages
        </Link>
      </header>
      <main id="contenu" className={styles.contenu}>
        <div key={clePage(pathname)} className={styles.page}>
          {page}
        </div>
      </main>
      {/* Retour arrière : position de défilement restaurée ; nouvelle page :
          en haut. Les liens vers la visionneuse passent preventScrollReset. */}
      <ScrollRestoration />
    </div>
  );
}
