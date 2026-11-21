import { describe, expect, it } from "vitest";
import { mosaiquePleinEcran } from "./rangees";

describe("mosaïque plein écran", () => {
  const ratios = [0.75, 0.75, 1.33, 1.33, 3.2, 3.5, 1.78];
  const pages = mosaiquePleinEcran(ratios, 1920, 986);

  it("deux photos par écran, dans l'ordre ; la dernière d'un nombre impair est seule", () => {
    expect(pages.map((p) => [p.debut, p.cases.length])).toEqual([[0, 2], [2, 2], [4, 2], [6, 1]]);
    expect(pages.at(-1)!.gabarit).toBe("seule");
  });

  it("les cases remplissent l'écran exactement", () => {
    for (const p of pages) expect(p.cases.reduce((a, c) => a + c.l * c.h, 0)).toBeCloseTo(1, 9);
  });

  it("côte à côte en général, l'une sur l'autre pour des panoramas", () => {
    expect(pages[0].gabarit).toBe("deux-colonnes");
    expect(pages[1].gabarit).toBe("deux-colonnes");
    expect(pages[2].gabarit).toBe("deux-lignes");
  });
});
