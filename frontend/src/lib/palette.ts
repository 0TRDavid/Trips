import type { CSSProperties } from "react";
import type { Palette } from "../api/types";

/**
 * Variables CSS d'une palette (calculée par le serveur, contrastes AA déjà
 * garantis). Posées sur le cadre d'une page, elles teintent tout ce qu'il
 * contient : les composants n'utilisent que ces variables.
 *
 * - `--accent` : couleur de TEXTE accentuée (accent_texte, lisible sur le fond) ;
 * - `--accent-vif` : l'accent franc, pour les surfaces et les filets ;
 * - `--sur-accent` : texte posé sur `--accent-vif` ;
 * - `--papier`, `--papier-2` : fonds teintés ;
 * - `--degrade` : dégradé des teintes du voyage ou du jour.
 */
export function variablesPalette(palette: Palette | undefined | null): CSSProperties {
  if (!palette) return {};
  return {
    "--accent": palette.accent_texte,
    "--accent-vif": palette.accent,
    "--sur-accent": palette.sur_accent,
    "--papier": palette.fond,
    "--papier-2": palette.fond_2,
    "--degrade": `linear-gradient(90deg, ${palette.degrade.join(", ")})`,
  } as CSSProperties;
}
