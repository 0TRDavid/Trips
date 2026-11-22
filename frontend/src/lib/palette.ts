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
 * - `--degrade` : dégradé des teintes du voyage ou du jour ;
 * - `--halo-1..3` : pastels des halos du fond (composants/FondPage.tsx).
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
    "--halo-1": palette.halos[0],
    "--halo-2": palette.halos[1],
    "--halo-3": palette.halos[2],
  } as CSSProperties;
}

/** Photo claire (luminance relative > 0,45) : titre sombre sur voile clair. */
export function estClaire(hex: string): boolean {
  const m = hex.match(/^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i);
  if (!m) return false;
  const [r, g, b] = m.slice(1).map((x) => {
    const c = parseInt(x, 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.45;
}
