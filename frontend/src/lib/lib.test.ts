import { describe, expect, it } from "vitest";
import type { PhotoResume, PointTrace } from "../api/types";
import { decisionGlissement } from "../hooks/useGlissement";
import { cadrageJour, ligneTrace } from "./carte";
import { dateCourte, dateLongue, estDateJour, heureLocale, libelleHeure, momentsParHeure, numeroJour, periode } from "./dates";
import { ratio, srcParDefaut, srcset } from "./rendus";
import { aUneVideo, formatDuree, sourceVideo } from "./videos";

const photo: PhotoResume = {
  id: 14,
  largeur: 3024,
  hauteur: 4032,
  couleur: "#908d84",
  placeholder: "HQgKDQIYZ292+oZGiXh4aIFBIDcE",
  rendus: {
    miniature: { url: "/m/14-mini.webp", largeur: 300, hauteur: 400 },
    moyenne: { url: "/m/14-moy.webp", largeur: 960, hauteur: 1280 },
    grande: { url: "/m/14-gr.webp", largeur: 1920, hauteur: 2560 },
  },
};

describe("rendus", () => {
  it("construit un srcset du plus petit au plus grand", () => {
    expect(srcset(photo)).toBe("/m/14-mini.webp 300w, /m/14-moy.webp 960w, /m/14-gr.webp 1920w");
  });
  it("ignore les rendus manquants", () => {
    const p = { ...photo, rendus: { grande: photo.rendus.grande } };
    expect(srcset(p)).toBe("/m/14-gr.webp 1920w");
    expect(srcParDefaut(p)).toBe("/m/14-gr.webp");
  });
  it("calcule le ratio, 1 si les dimensions manquent", () => {
    expect(ratio(photo)).toBeCloseTo(0.75);
    expect(ratio({ ...photo, largeur: 0 })).toBe(1);
  });
});

describe("dates", () => {
  it("formate en français sans décalage de fuseau", () => {
    expect(dateLongue("2025-06-01")).toBe("dimanche 1 juin 2025");
    expect(dateCourte("2025-05-31")).toBe("31 mai");
  });
  it("formate une période", () => {
    expect(periode("2025-05-31", "2025-06-09")).toBe("31 mai – 9 juin 2025");
    expect(periode("2025-06-03", "2025-06-09")).toBe("3 – 9 juin 2025");
    expect(periode("2025-06-03", "2025-06-03")).toBe("3 juin 2025");
    expect(periode("2025-12-28", "2026-01-04")).toBe("28 décembre 2025 – 4 janvier 2026");
  });
  it("numérote les jours", () => {
    expect(numeroJour("2025-05-31", "2025-05-31")).toBe(1);
    expect(numeroJour("2025-05-31", "2025-06-09")).toBe(10);
  });
  it("garde l'heure locale du voyage telle quelle", () => {
    expect(heureLocale("2025-06-02T09:56:24+09:00")).toBe("09:56");
    expect(heureLocale(null)).toBe("");
  });
  it("valide une date de jour", () => {
    expect(estDateJour("2025-06-02")).toBe(true);
    expect(estDateJour("2025-02-30")).toBe(false);
    expect(estDateJour("hier")).toBe(false);
  });
});

describe("carte", () => {
  const trace: PointTrace[] = [
    { lat: 45.7, lon: 5.07, jour: "2025-05-31" },
    { lat: 52.3, lon: 4.77, jour: "2025-05-31" },
    { lat: 35.68, lon: 139.76, jour: "2025-06-06" },
  ];
  it("cadre un jour sur les bornes de ses points", () => {
    expect(cadrageJour(trace, "2025-05-31")).toEqual({
      type: "bornes",
      bornes: [4.77, 45.7, 5.07, 52.3],
    });
  });
  it("centre sur un point unique, rien pour un jour sans position", () => {
    expect(cadrageJour(trace, "2025-06-06")).toEqual({ type: "point", lon: 139.76, lat: 35.68 });
    expect(cadrageJour(trace, "2025-06-09")).toEqual({ type: "aucun" });
  });
  it("ne trace une ligne qu'à partir de deux points", () => {
    expect(ligneTrace(trace).features).toHaveLength(1);
    expect(ligneTrace(trace.slice(0, 1)).features).toHaveLength(0);
  });
});

describe("glissement", () => {
  it("reconnaît un glissement à gauche (suivant) et à droite (précédent)", () => {
    expect(decisionGlissement(-120, 10, 300)).toBe("suivant");
    expect(decisionGlissement(120, -5, 300)).toBe("precedent");
  });
  it("accepte un geste court mais rapide", () => {
    expect(decisionGlissement(-40, 0, 50)).toBe("suivant");
  });
  it("ignore un défilement vertical ou un geste trop petit", () => {
    expect(decisionGlissement(-70, 200, 300)).toBeNull();
    expect(decisionGlissement(-20, 0, 30)).toBeNull();
    expect(decisionGlissement(-50, 0, 500)).toBeNull();
  });
});

describe("moments de la journée", () => {
  const p = (id: number, prise_le: string | null) => ({ id, prise_le });

  it("regroupe les photos consécutives de la même heure, dans l'ordre reçu", () => {
    const moments = momentsParHeure([
      p(1, "2025-06-01T09:05:00+09:00"),
      p(2, "2025-06-01T09:59:00+09:00"),
      p(3, "2025-06-01T14:16:00+09:00"),
      p(4, "2025-06-01T14:30:00+09:00"),
    ]);
    expect(moments.map((m) => [m.heure, m.photos.map((x) => x.id)])).toEqual([
      [9, [1, 2]],
      [14, [3, 4]],
    ]);
  });
  it("lit l'heure locale du voyage, sans conversion", () => {
    expect(momentsParHeure([p(1, "2025-06-01T23:30:00+09:00")])[0].heure).toBe(23);
  });
  it("une heure qui revient plus loin (ordre retouché) ouvre un nouveau moment", () => {
    const heures = momentsParHeure([
      p(1, "2025-06-01T10:00:00+09:00"),
      p(2, "2025-06-01T11:00:00+09:00"),
      p(3, "2025-06-01T10:30:00+09:00"),
    ]).map((m) => m.heure);
    expect(heures).toEqual([10, 11, 10]);
  });
  it("met les photos sans heure à part", () => {
    expect(momentsParHeure([p(1, null), p(2, null)])).toEqual([{ heure: null, photos: [p(1, null), p(2, null)] }]);
    expect(momentsParHeure([])).toEqual([]);
  });
  it("libellés", () => {
    expect(libelleHeure(9)).toBe("9 h");
    expect(libelleHeure(0)).toBe("0 h");
    expect(libelleHeure(null)).toBe("Heure inconnue");
  });
});

describe("vidéos", () => {
  const videos = {
    "720": { url: "/m/v-720.mp4", largeur: 720, hauteur: 1280 },
    "1080": { url: "/m/v-1080.mp4", largeur: 1080, hauteur: 1920 },
  };
  it("prend le 720p tant qu'il suffit, le 1080p au-delà", () => {
    expect(sourceVideo({ videos }, 320)?.url).toBe("/m/v-720.mp4"); // vignette
    expect(sourceVideo({ videos }, 320, 2)?.url).toBe("/m/v-720.mp4"); // vignette sur écran Retina
    expect(sourceVideo({ videos }, 400, 2)?.url).toBe("/m/v-1080.mp4"); // téléphone en plein écran
    expect(sourceVideo({ videos }, 1080)?.url).toBe("/m/v-1080.mp4"); // ordinateur en plein écran
  });
  it("se replie sur le seul rendu d'une petite source", () => {
    expect(sourceVideo({ videos: { "720": videos["720"] } }, 1080)?.url).toBe("/m/v-720.mp4");
    expect(sourceVideo({ videos: {} }, 300)).toBeUndefined();
  });
  it("formate les durées", () => {
    expect(formatDuree(3.14)).toBe("0:03");
    expect(formatDuree(54.12)).toBe("0:54");
    expect(formatDuree(65)).toBe("1:05");
    expect(formatDuree(3725)).toBe("1:02:05");
    expect(formatDuree(null)).toBe("");
    expect(formatDuree(Number.NaN)).toBe("");
  });
  it("sait si un média a une vidéo à lire", () => {
    expect(aUneVideo({ type: "photo", videos: {} })).toBe(false);
    expect(aUneVideo({ type: "animee", videos })).toBe(true);
    expect(aUneVideo({ type: "video", videos: {} })).toBe(false); // rendus pas encore générés
  });
});
