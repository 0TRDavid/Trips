import type { PhotoJour, Rendu } from "../api/types";

/**
 * Choisit le rendu vidéo à charger : le 720p suffit tant que le petit côté
 * affiché (en pixels physiques) ne dépasse pas ~720 ; au-delà, le 1080p.
 * Repli sur ce qui existe (une source petite n'a qu'un rendu).
 */
export function sourceVideo(
  media: Pick<PhotoJour, "videos">,
  petitCoteAffiche: number,
  densite = 1,
): Rendu | undefined {
  const { videos } = media;
  const besoin = petitCoteAffiche * densite;
  const prefere = besoin > 760 ? videos["1080"] : videos["720"];
  return prefere ?? videos["720"] ?? videos["1080"];
}

/** 3.14 → "0:03", 54.1 → "0:54", 65 → "1:05", 3725 → "1:02:05". */
export function formatDuree(secondes: number | null | undefined): string {
  if (secondes == null || !Number.isFinite(secondes) || secondes < 0) return "";
  const total = Math.round(secondes);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/** Vrai si le média a de quoi être animé ou lu. */
export function aUneVideo(media: Pick<PhotoJour, "type" | "videos">): boolean {
  return media.type !== "photo" && Object.keys(media.videos).length > 0;
}
