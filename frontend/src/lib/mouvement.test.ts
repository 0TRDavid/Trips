import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { GenreNavigation, Navigation } from "./mouvement";
import {
  REGLAGES_DEFAUT,
  apparitionPhoto,
  barreJour,
  ouverturePleinEcran,
  arriveeTitre,
  roulementHeure,
  enregistrerReglages,
  entree,
  sortie,
  variantesBloc,
  variantesPage,
  variantesPhotoVoisine,
  volPhoto,
  volEnTete,
} from "./mouvement";
import { ecranDe, genreNavigation, navigation, sensNavigation } from "./navigation";
import { echantillonner, echelleCouverture, etatVol } from "./vol";

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
    expect(genreNavigation(voyage, j1)).toBe("ouvrirJour");
    expect(genreNavigation(j1, voyage)).toBe("ouvrirJour");
    expect(genreNavigation("/voyages/autre", j1)).toBe("page");
    expect(genreNavigation("/voyages/a/jours/2025-06-01", "/voyages/b/jours/2025-06-02")).toBe("page");
  });

  it("mouvement réduit = fondu ; retour déjà animé par le navigateur = aucune", () => {
    expect(navigation(j1, j2, { reduit: true, dejaAnime: false })).toEqual({ genre: "fondu", sens: 1 });
    expect(navigation(j2, j1, { reduit: false, dejaAnime: true })).toEqual({ genre: "aucune", sens: -1 });
  });
});

describe("règles du système de mouvement", () => {
  // Seulement transform et opacity, écrits tels quels : x / y / scale de Motion
  // seraient calculés sur le fil principal et saccaderaient.
  const PERMISES = new Set(["opacity", "transform", "transition", "transitionEnd"]);
  const genres: GenreNavigation[] = ["aucune", "fondu", "voyage", "ouvrirJour", "jour", "page"];
  const resoudre = (v: unknown, custom: unknown) => (typeof v === "function" ? v(custom) : v) as Record<string, unknown>;

  it("n'anime que transform (translate / scale) et opacity, accélérables par le navigateur", () => {
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
          const v = resoudre(etape, custom);
          for (const prop of Object.keys(v)) expect(PERMISES).toContain(prop);
          if (v.transform) expect(String(v.transform)).toMatch(/^(none|(translate|scale)\([^)]*\)\s*)+$/);
          // Une entrée ne laisse aucun transform derrière elle (repère des position: fixed).
          if (v.transitionEnd) expect(v.transitionEnd).toEqual({ transform: "none" });
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
      expect(duree(volEnTete(-1))).toBeLessThan(duree(volEnTete(1)));
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
      const x = (sens: 1 | -1) => resoudre(variantesPage.initial, { genre: "jour", sens }).transform;
      const signe = (v: unknown) => Math.sign(parseFloat(String(v).replace("translate(", "")));
      expect(signe(x(1))).toBe(1);
      expect(signe(x(-1))).toBe(-1);
      // L'ancienne page part du côté opposé.
      expect(signe(resoudre(variantesPage.sortie, { genre: "jour", sens: 1 }).transform)).toBe(-1);
    }
  });

  it("mouvement réduit : un simple fondu, sans déplacement", () => {
    for (const etape of ["initial", "visible", "sortie"] as const) {
      const v = resoudre(variantesPage[etape], { genre: "fondu", sens: 1 });
      expect(v.transform ?? "translate(0%, 0px)").toBe("translate(0%, 0px)");
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

describe("trajectoire précalculée du vol", () => {
  it("un ressort part de 0, finit exactement à 1, avec un léger dépassement", () => {
    const { avancements, duree } = echantillonner(volEnTete(1));
    expect(avancements[0]).toBe(0);
    expect(avancements.at(-1)).toBe(1);
    expect(Math.max(...avancements)).toBeGreaterThan(1); // rebond (bounce 0,12)
    expect(Math.max(...avancements)).toBeLessThan(1.1);
    expect(duree).toBeGreaterThan(300);
    expect(duree).toBeLessThan(2000);
  });

  it("une courbe de Bézier est échantillonnée sur sa durée", () => {
    const { avancements, duree } = echantillonner({ duration: 0.5, ease: [0.16, 1, 0.3, 1] });
    expect(duree).toBe(500);
    expect(avancements[0]).toBe(0);
    expect(avancements.at(-1)).toBeCloseTo(1);
    expect(avancements[3]).toBeGreaterThan(3 / avancements.length); // expo-out : rapide au début
  });
});

describe("page jour : défilement", () => {
  it("une apparition finit sans transform, garde son état de départ pendant le délai, et son décalage est plafonné", () => {
    for (const v of ["fondu", "montee", "cascade"] as const) {
      const a = apparitionPhoto(v, false, 3)!;
      const fin = a.images.at(-1)!;
      expect(fin.opacity).toBe(1);
      expect(fin.transform ?? "none").toBe("none");
      expect(a.options.fill).toBe("backwards");
      expect(apparitionPhoto(v, false, 50)!.options.delay).toBe(apparitionPhoto(v, false, 6)!.options.delay);
    }
    expect(apparitionPhoto("aucune", false, 0)).toBeNull();
  });

  it("mouvement réduit : un fondu, sans déplacement ni délai", () => {
    const a = apparitionPhoto("cascade", true, 4)!;
    expect(a.images.some((i) => "transform" in i)).toBe(false);
    expect(a.options.delay).toBe(0);
    const r = roulementHeure(1, true);
    expect([...r.entree.images, ...r.sortie.images].some((i) => "transform" in i)).toBe(false);
  });

  it("le roulement d'heure : entrée finie sans transform, sortie plus courte, sens respecté", () => {
    const bas = roulementHeure(1, false);
    const haut = roulementHeure(-1, false);
    expect(bas.entree.images.at(-1)!.transform).toBe("none");
    expect(Number(bas.sortie.options.duration)).toBeLessThan(Number(bas.entree.options.duration));
    expect(bas.entree.images[0].transform).not.toBe(haut.entree.images[0].transform);
  });

  it("ouverture plein écran : photo jamais déformée, titre collé à son bas puis à sa place", () => {
    const m = { haut: 100, bandeau: 600, plein: 900, basTitre: 900 };
    const o = ouverturePleinEcran(m);
    const nombres = (t: string) => [...t.matchAll(/-?\d+(?:\.\d+)?(?:e-?\d+)?/g)].map((x) => Number(x[0]));
    o.cadre.transform.forEach((c, i) => {
      const [, s] = nombres(c);
      const [, ty, , k] = nombres(o.photo.transform[i]);
      expect(s * k).toBeCloseTo(1, 9); // contre-échelle exacte
      expect(ty + (m.plein * k) / 2).toBeCloseTo(m.bandeau / 2, 6); // photo centrée
      // Tant que le titre est clair (posé sur la photo), il est au-dessus de son bord.
      if (o.titreSurPhoto.opacity[i] === 1) {
        const [, dy] = nombres(o.titreSurPhoto.transform[i]);
        expect(m.basTitre + dy).toBeLessThanOrEqual(m.haut + m.bandeau * s);
      }
    });
    expect(nombres(o.cadre.transform[0])[1]).toBeCloseTo(1.5, 9); // jusqu'au bas de l'écran
    expect(o.cadre.transform.at(-1)).toBe("scale(1, 1)"); // puis la taille du bandeau
    expect(o.titre.transform.at(-1)).toBe("translate(0px, 0px)"); // titre à sa place
    expect(o.titre.opacity.at(-1)).toBe(1);
    expect(o.titreSurPhoto.opacity.at(-1)).toBe(0);
  });

  it("le titre arrive de la gauche et finit sans transform", () => {
    const a = arriveeTitre(false);
    expect(a.images.at(-1)).toEqual({ opacity: 1, transform: "none" });
    expect(Object.keys(arriveeTitre(true).images[0])).toEqual(["opacity"]);
  });

  it("barre du jour : entrée qui finit sans transform, sortie plus courte", () => {
    const entree = barreJour(true, false);
    const sortie = barreJour(false, false);
    expect(entree.images.at(-1)).toEqual({ opacity: 1, transform: "none" });
    expect(Number(sortie.options.duration)).toBeLessThan(Number(entree.options.duration));
    expect(Object.keys(barreJour(true, true).images[0])).toEqual(["opacity"]);
  });
});
