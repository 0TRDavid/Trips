import { createContext, useContext, useLayoutEffect } from "react";
import type { Palette } from "../api/types";
import type { Navigation } from "../lib/mouvement";

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
