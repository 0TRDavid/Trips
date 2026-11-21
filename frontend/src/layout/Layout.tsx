import { useEffect, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import { Link, ScrollRestoration, useLocation, useOutlet } from "react-router";
import { AnimatePresence, motion, useIsPresent } from "motion/react";
import { mouvementReduit } from "../hooks/useMouvementReduit";
import { clePage } from "../lib/chemins";
import type { Navigation } from "../lib/mouvement";
import { variantesPage } from "../lib/mouvement";
import { consommerRetourDejaAnime, navigation } from "../lib/navigation";
import { arreterVol } from "../lib/vol";
import type { Palette } from "../api/types";
import FondPage from "../composants/FondPage";
import { variablesPalette } from "../lib/palette";
import { ContexteNavigation, ContexteTeinte } from "./contexte";
import styles from "./Layout.module.css";

/**
 * Cadre commun à toutes les pages, jamais démonté.
 *
 * La page courante est récupérée avec useOutlet() et identifiée par une clé
 * (`clePage`, qui ignore la visionneuse). Quand la clé change,
 * AnimatePresence garde l'ancienne page le temps de sa sortie pendant que la
 * nouvelle entre ; la transition dépend de la navigation (genre et sens,
 * lib/navigation.ts), y compris pour le bouton retour du navigateur.
 */
export default function Layout() {
  const page = useOutlet();
  const { pathname } = useLocation();
  const cle = clePage(pathname);

  // Navigation calculée UNE fois par changement de page, pendant le rendu
  // (et non dans un effet) : la nouvelle page doit naître avec la bonne
  // transition. Premier affichage ou lien direct : aucune animation.
  const [etat, setEtat] = useState<{ cle: string; nav: Navigation }>({ cle, nav: { genre: "aucune", sens: 1 } });
  if (etat.cle !== cle) {
    arreterVol();
    setEtat({
      cle,
      nav: navigation(etat.cle, cle, { reduit: mouvementReduit(), dejaAnime: consommerRetourDejaAnime() }),
    });
  }
  const nav = etat.cle === cle ? etat.nav : { genre: "aucune" as const, sens: 1 as const };

  return (
    <ContexteNavigation.Provider value={nav}>
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
          <AnimatePresence initial={false} custom={nav}>
            <CadrePage key={cle} nav={nav}>
              {page}
            </CadrePage>
          </AnimatePresence>
        </main>
        {/* Retour arrière : position de défilement restaurée ; nouvelle page :
            en haut. Les liens vers la visionneuse passent preventScrollReset. */}
        <ScrollRestoration />
      </div>
    </ContexteNavigation.Provider>
  );
}

/**
 * Une page, animée à l'entrée et à la sortie.
 *
 * La page qui sort est FIGÉE à l'écran (position fixe, à l'endroit exact où
 * on la voyait) : la nouvelle page remet le défilement en haut, ou le
 * restaure au retour, sans que l'ancienne saute pendant sa sortie. Elle passe
 * sous la nouvelle et ne reçoit plus de clics.
 */
function CadrePage({ nav, children }: { nav: Navigation; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const present = useIsPresent();
  const fige = useRef<{ top: number; left: number; width: number } | null>(null);
  // Lu pendant le rendu de sortie : le défilement n'a pas encore bougé (la
  // restauration a lieu après, dans un effet de ScrollRestoration).
  if (!present && !fige.current && ref.current) {
    const r = ref.current.getBoundingClientRect();
    fige.current = { top: r.top, left: r.left, width: r.width };
  }
  // Palette de la page (voyage, jour), déclarée par la page via usePalette().
  const [palette, setPalette] = useState<Palette | null>(null);
  // La gouttière de la barre de défilement (hors des pages) prend le fond de
  // la page affichée, sinon une bande de papier neutre reste visible à droite.
  useEffect(() => {
    if (!present) return;
    document.documentElement.style.setProperty("--fond-gouttiere", palette?.fond ?? "");
  }, [present, palette]);
  const style: CSSProperties = {
    ...variablesPalette(palette),
    ...(fige.current && { position: "fixed", ...fige.current, zIndex: 0, pointerEvents: "none" }),
  };

  return (
    <motion.div
      ref={ref}
      className={styles.page}
      style={style}
      custom={nav}
      variants={variantesPage}
      initial="initial"
      animate="visible"
      exit="sortie"
      inert={!present || undefined}
    >
      <FondPage />
      <ContexteTeinte.Provider value={setPalette}>{children}</ContexteTeinte.Provider>
    </motion.div>
  );
}
