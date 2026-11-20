// Formatage des dates en français.
//
// Deux sortes de dates arrivent de l'API :
// - les dates de jour « AAAA-MM-JJ » : un jour du calendrier local du voyage,
//   sans heure. On les lit en UTC pour qu'aucun fuseau du navigateur ne les
//   décale d'un jour ;
// - `prise_le` « 2025-06-02T09:56:24+09:00 » : déjà exprimée à l'heure locale
//   du voyage. On en extrait l'heure telle quelle, sans conversion.

function jourUtc(iso: string): Date {
  const [a, m, j] = iso.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, j));
}

const fmtLong = new Intl.DateTimeFormat("fr-FR", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});
const fmtCourt = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  timeZone: "UTC",
});
const fmtCourtAnnee = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});
const fmtJourSemaine = new Intl.DateTimeFormat("fr-FR", { weekday: "short", timeZone: "UTC" });

/** « mardi 3 juin 2025 » */
export function dateLongue(iso: string): string {
  return fmtLong.format(jourUtc(iso));
}

/** « 3 juin » */
export function dateCourte(iso: string): string {
  return fmtCourt.format(jourUtc(iso));
}

/** « mar. » */
export function jourSemaine(iso: string): string {
  return fmtJourSemaine.format(jourUtc(iso));
}

/** « 31 mai – 9 juin 2025 », « 3 – 9 juin 2025 », « 28 déc. 2025 – 4 janv. 2026 » */
export function periode(debut: string | null, fin: string | null): string {
  if (!debut) return "";
  if (!fin || fin === debut) return fmtCourtAnnee.format(jourUtc(debut));
  const d = jourUtc(debut);
  const f = jourUtc(fin);
  if (d.getUTCFullYear() !== f.getUTCFullYear()) {
    return `${fmtCourtAnnee.format(d)} – ${fmtCourtAnnee.format(f)}`;
  }
  if (d.getUTCMonth() === f.getUTCMonth()) {
    return `${d.getUTCDate()} – ${fmtCourtAnnee.format(f)}`;
  }
  return `${fmtCourt.format(d)} – ${fmtCourtAnnee.format(f)}`;
}

/** Numéro du jour dans le voyage (1 pour le premier). */
export function numeroJour(debut: string | null, date: string): number | null {
  if (!debut) return null;
  return Math.round((jourUtc(date).getTime() - jourUtc(debut).getTime()) / 86_400_000) + 1;
}

/** « 09:56 » à partir de « 2025-06-02T09:56:24+09:00 » (heure locale du voyage). */
export function heureLocale(priseLe: string | null): string {
  const m = priseLe?.match(/T(\d{2}):(\d{2})/);
  return m ? `${m[1]}:${m[2]}` : "";
}

/** Une date de jour valide « AAAA-MM-JJ » (évite d'appeler l'API pour rien). */
export function estDateJour(valeur: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(valeur)) return false;
  const d = jourUtc(valeur);
  return d.toISOString().slice(0, 10) === valeur;
}

/** « 6 photos », « 1 photo » */
export function pluriel(n: number, singulier: string, plurielForme = `${singulier}s`): string {
  return `${n} ${n > 1 ? plurielForme : singulier}`;
}
