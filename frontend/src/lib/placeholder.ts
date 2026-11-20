import { thumbHashToDataURL } from "thumbhash";

// Décoder un ThumbHash coûte peu, mais une galerie en affiche des dizaines et
// React peut re-rendre souvent : on garde le résultat par hash.
const cache = new Map<string, string | null>();

/** Image PNG (data URL) floue et au bon ratio, ou null si le hash est invalide. */
export function placeholderDataUrl(hash: string): string | null {
  if (!hash) return null;
  const connu = cache.get(hash);
  if (connu !== undefined) return connu;
  let url: string | null = null;
  try {
    const octets = Uint8Array.from(atob(hash), (c) => c.charCodeAt(0));
    url = thumbHashToDataURL(octets);
  } catch {
    url = null;
  }
  cache.set(hash, url);
  return url;
}
