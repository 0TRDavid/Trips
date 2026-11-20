import { describe, expect, it } from "vitest";
import type { PhotoResume, PointTrace } from "../api/types";
import { decisionGlissement } from "../hooks/useGlissement";
import { cadrageJour, ligneTrace } from "./carte";
import { dateCourte, dateLongue, estDateJour, heureLocale, numeroJour, periode } from "./dates";
import { ratio, srcParDefaut, srcset } from "./rendus";

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
