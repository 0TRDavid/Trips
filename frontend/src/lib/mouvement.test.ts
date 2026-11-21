import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GenreNavigation, Navigation } from "./mouvement";
import {
  REGLAGES_DEFAUT,
  enregistrerReglages,
  entree,
  sortie,
  variantesBloc,
  variantesPage,
  variantesPhotoVoisine,
  volPhoto,
  volVoyage,
} from "./mouvement";
import { ecranDe, genreNavigation, navigation, sensNavigation } from "./navigation";
import { echelleCouverture, etatVol } from "./vol";

// Réglages du labo en mémoire (pas de navigateur sous Vitest).
beforeEach(() => {
  const stock = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => stock.get(k) ?? null,
    setItem: (k: string, v: string) => void stock.set(k, v),
  });
  vi.stubGlobal("window", { dispatchEvent: () => true, addEventListener: () => {} });
  enregistrerReglages(REGLAGES_DEFAUT);
});
afterEach(() => vi.unstubAllGlobals());

describe("sens et genre de navigation", () => {
  const voyage = "/voyages/japon-2025";
  const j1 = "/voyages/japon-2025/jours/2025-06-01";
  const j2 = "/voyages/japon-2025/jours/2025-06-02";

  it("reconnaît les écrans", () => {
    expect(ecranDe("/")).toEqual({ niveau: 0 });
    expect(ecranDe(voyage)).toEqual({ niveau: 1, slug: "japon-2025" });
    expect(ecranDe(j1)).toEqual({ niveau: 2, slug: "japon-2025", date: "2025-06-01" });
    expect(ecranDe("/nimporte/quoi")).toEqual({ niveau: -1 });
  });

  it("avance en descendant, recule en remontant : le retour est l'inverse de l'aller", () => {
    for (const [a, b] of [["/", voyage], [voyage, j1], ["/", j1]]) {
      expect(sensNavigation(a, b)).toBe(1);
      expect(sensNavigation(b, a)).toBe(-1);
    }
  });

  it("entre deux jours, le sens suit les dates (jour précédent = retour)", () => {
    expect(sensNavigation(j1, j2)).toBe(1);
    expect(sensNavigation(j2, j1)).toBe(-1);
    expect(genreNavigation(j1, j2)).toBe("jour");
  });

  it("genres : voyage entre l'accueil et un voyage, page sinon", () => {
    expect(genreNavigation("/", voyage)).toBe("voyage");
    expect(genreNavigation(voyage, "/")).toBe("voyage");
    expect(genreNavigation(voyage, j1)).toBe("page");
    expect(genreNavigation("/voyages/a/jours/2025-06-01", "/voyages/b/jours/2025-06-02")).toBe("page");
  });

  it("mouvement réduit = fondu ; retour déjà animé par le navigateur = aucune", () => {
    expect(navigation(j1, j2, { reduit: true, dejaAnime: false })).toEqual({ genre: "fondu", sens: 1 });
    expect(navigation(j2, j1, { reduit: false, dejaAnime: true })).toEqual({ genre: "aucune", sens: -1 });
  });
});

describe("règles du système de mouvement", () => {
  const PERMISES = new Set(["opacity", "x", "y", "scale", "transition"]);
  const genres: GenreNavigation[] = ["aucune", "fondu", "voyage", "jour", "page"];
  const resoudre = (v: unknown, custom: unknown) => (typeof v === "function" ? v(custom) : v) as Record<string, unknown>;

  it("n'anime que transform (x, y, scale) et opacity", () => {
    {
      const ensembles = [
        ...genres.flatMap((genre) =>
          ([1, -1] as const).map((sens) => [variantesPage, { genre, sens } satisfies Navigation] as const),
        ),
        ...[false, true].map((r) => [variantesBloc(r), undefined] as const),
        ...[false, true].flatMap((r) => ([1, -1] as const).map((sens) => [variantesPhotoVoisine(r), sens] as const)),
      ];
      for (const [variantes, custom] of ensembles) {
        for (const etape of Object.values(variantes)) {
          for (const prop of Object.keys(resoudre(etape, custom))) expect(PERMISES).toContain(prop);
        }
      }
    }
  });

  it("une sortie est plus rapide que l'entrée correspondante", () => {
    for (const d of [0.18, 0.32, 0.55]) {
      expect(sortie(d).duration!).toBeLessThan(entree(d).duration!);
    }
    {
      const duree = (t: { visualDuration?: number; duration?: number }) => t.visualDuration ?? t.duration ?? 0;
      expect(duree(volVoyage(-1))).toBeLessThan(duree(volVoyage(1)));
      expect(duree(volPhoto(-1))).toBeLessThan(duree(volPhoto(1)));
      for (const sens of [1, -1] as const) {
        const nav = { genre: "page", sens } satisfies Navigation;
        const entreePage = resoudre(variantesPage.visible, nav).transition as { duration: number };
        const sortiePage = resoudre(variantesPage.sortie, nav).transition as { duration: number };
        expect(sortiePage.duration).toBeLessThan(entreePage.duration);
      }
      const jour = (etape: "visible" | "sortie") =>
        (resoudre(variantesPage[etape], { genre: "jour", sens: 1 }).transition as { duration: number }).duration;
      expect(jour("sortie")).toBeLessThan(jour("visible"));
    }
  });

  it("le glissement change de côté avec le sens de navigation", () => {
    {
      const x = (sens: 1 | -1) => resoudre(variantesPage.initial, { genre: "jour", sens }).x;
      const signe = (v: unknown) => Math.sign(typeof v === "string" ? parseFloat(v) : Number(v));
      expect(signe(x(1))).toBe(1);
      expect(signe(x(-1))).toBe(-1);
      // L'ancienne page part du côté opposé.
      expect(signe(resoudre(variantesPage.sortie, { genre: "jour", sens: 1 }).x)).toBe(-1);
    }
  });

  it("mouvement réduit : un simple fondu, sans déplacement", () => {
    for (const etape of ["initial", "visible", "sortie"] as const) {
      const v = resoudre(variantesPage[etape], { genre: "fondu", sens: 1 });
      expect(v.x ?? 0).toBe(0);
      expect(v.y ?? 0).toBe(0);
    }
    expect(Object.keys(resoudre(variantesPhotoVoisine(true).initial, 1))).toEqual(["opacity"]);
  });

  it("le ralenti du labo multiplie les durées", () => {
    const normale = entree(0.32).duration!;
    enregistrerReglages({ ...REGLAGES_DEFAUT, ralenti: 4 });
    expect(entree(0.32).duration).toBeCloseTo(normale * 4);
  });
});

describe("vol d'un élément partagé", () => {
  const carte = { x: 48, y: 190, w: 400, h: 500 }; // 4:5
  const entete = { x: 48, y: 54, w: 1170, h: 200 }; // très large
  const photo = { w: 4032, h: 3024 }; // 4:3

  const transforms = (p: number) => {
    const { boite, image } = etatVol(carte, entete, photo, p);
    const [tx, ty, sx, sy] = boite.match(/-?[\d.]+(e-?\d+)?/g)!.map(Number);
    const [ix, iy] = image.match(/-?[\d.]+(e-?\d+)?/g)!.map(Number);
    return { tx, ty, sx, sy, ix, iy };
  };

  it("part exactement du rectangle de départ et arrive sans transformation", () => {
    const debut = transforms(0);
    expect(entete.x + debut.tx).toBeCloseTo(carte.x);
    expect(entete.y + debut.ty).toBeCloseTo(carte.y);
    expect(entete.w * debut.sx).toBeCloseTo(carte.w);
    expect(entete.h * debut.sy).toBeCloseTo(carte.h);
    const fin = transforms(1);
    expect([fin.tx, fin.ty, fin.sx, fin.sy, fin.ix, fin.iy]).toEqual([0, 0, 1, 1, 1, 1]);
  });

  it("à chaque instant, la photo couvre la boîte sans être déformée", () => {
    const base = echelleCouverture(entete, photo);
    for (const p of [0, 0.25, 0.5, 0.75, 1, 1.08]) {
      const t = transforms(p);
      // Échelle réelle de la photo à l'écran, horizontalement et verticalement.
      const ex = base * t.sx * t.ix;
      const ey = base * t.sy * t.iy;
      expect(ex).toBeCloseTo(ey, 6); // pas d'étirement
      const boite = { w: entete.w * t.sx, h: entete.h * t.sy };
      expect(ex).toBeCloseTo(echelleCouverture(boite, photo), 6); // couvre exactement (object-fit: cover)
    }
  });
});
