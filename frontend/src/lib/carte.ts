import type { PointTrace } from "../api/types";

/** [ouest, sud, est, nord] */
export type Bornes = [number, number, number, number];

/** Ce qu'il faut faire pour « zoomer sur les photos d'un jour ». */
export type CadrageJour =
  | { type: "bornes"; bornes: Bornes }
  | { type: "point"; lon: number; lat: number }
  | { type: "aucun" };

export function bornes(points: PointTrace[]): Bornes | null {
  if (points.length === 0) return null;
  let ouest = Infinity, sud = Infinity, est = -Infinity, nord = -Infinity;
  for (const p of points) {
    ouest = Math.min(ouest, p.lon);
    est = Math.max(est, p.lon);
    sud = Math.min(sud, p.lat);
    nord = Math.max(nord, p.lat);
  }
  return [ouest, sud, est, nord];
}

/**
 * Cadrage d'un jour. L'API ne donne pas les coordonnées de chaque photo
 * (règle de confidentialité), mais le tracé : ses points pour un jour sont
 * les positions des photos géolocalisées de ce jour, simplifiées à 30 m.
 * Un seul point (ou des points confondus) : on centre dessus à zoom fixe.
 */
export function cadrageJour(trace: PointTrace[], jour: string): CadrageJour {
  const b = bornes(trace.filter((p) => p.jour === jour));
  if (!b) return { type: "aucun" };
  const [ouest, sud, est, nord] = b;
  // ~100 m : en dessous, fitBounds zoomerait jusqu'au maximum.
  if (est - ouest < 0.001 && nord - sud < 0.001) {
    return { type: "point", lon: (ouest + est) / 2, lat: (sud + nord) / 2 };
  }
  return { type: "bornes", bornes: b };
}

/** GeoJSON du tracé : une ligne continue pour tout le voyage. */
export function ligneTrace(trace: PointTrace[]) {
  return {
    type: "FeatureCollection" as const,
    features:
      trace.length >= 2
        ? [
            {
              type: "Feature" as const,
              properties: {},
              geometry: {
                type: "LineString" as const,
                coordinates: trace.map((p) => [p.lon, p.lat]),
              },
            },
          ]
        : [],
  };
}

/** GeoJSON des points, chacun portant son jour (pour le clic et la mise en évidence). */
export function pointsTrace(trace: PointTrace[]) {
  return {
    type: "FeatureCollection" as const,
    features: trace.map((p) => ({
      type: "Feature" as const,
      properties: { jour: p.jour },
      geometry: { type: "Point" as const, coordinates: [p.lon, p.lat] },
    })),
  };
}
