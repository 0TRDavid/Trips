import { createContext, useContext, useEffect, useLayoutEffect, useState } from "react";
import type { Palette } from "../api/types";
import type { Navigation } from "../lib/mouvement";
import { avecEnTetePartage, dureeDe, volEnTete } from "../lib/mouvement";

/**
 * Dernière navigation entre pages (genre et sens), calculée par le Layout.
 * Les éléments partagés s'en servent pour savoir s'ils doivent « voler ».
 */
export const ContexteNavigation = createContext<Navigation>({ genre: "aucune", sens: 1 });

export const useNavigationPage = () => useContext(ContexteNavigation);

/** Déclare la palette de la page au cadre qui l'entoure (Layout). */
export const ContexteTeinte = createContext<(p: Palette | null) => void>(() => {});

/**
 * Teinte la page avec une palette tirée de ses photos : fond, accents,
 * dégradé (variables CSS, lib/palette.ts). Appliquée avant la première
 * peinture ; la page qui sort garde la sienne pendant sa sortie.
 */
export function usePalette(palette: Palette | null | undefined) {
  const definir = useContext(ContexteTeinte);
  useLayoutEffect(() => {
    definir(palette ?? null);
  }, [definir, palette]);
}

/**
 * Faux tant qu'une photo « vole » vers un en-tête ou en revient (accueil ↔
 * voyage, voyage ↔ jour), vrai ensuite ou tout de suite s'il n'y a pas de
 * vol. Sert à différer ce qui est lourd à monter (carte MapLibre, galerie
 * d'un jour) : le monter pendant le vol retarderait son départ.
 */
export function useApresVol(): boolean {
  const nav = useNavigationPage();
  const attente = avecEnTetePartage(nav) ? dureeDe(volEnTete(nav.sens)) : 0;
  const [pret, setPret] = useState(attente === 0);
  useEffect(() => {
    if (pret) return;
    const minuterie = setTimeout(() => setPret(true), attente * 1000 + 50);
    return () => clearTimeout(minuterie);
    // Au montage seulement.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return pret;
}
