import { describe, expect, it } from "vitest";
import { mosaiquePleinEcran } from "./rangees";

describe("mosaïque plein écran", () => {
  const ratios = [0.75, 0.75, 1.78, 0.75, 1.33, 0.56, 0.75, 0.75];
  const pages = mosaiquePleinEcran(ratios, 1806, 1026);

  it("paysages seuls, portraits par deux ; chaque photo une fois, dans l'ordre", () => {
    expect(pages.map((p) => [p.debut, p.cases.length])).toEqual([
      [0, 2],
      [2, 1],
      [3, 1],
      [4, 1],
      [5, 2],
      [7, 1],
    ]);
  });

  it("une photo seule remplit l'écran seulement si son format en est proche", () => {
    const seule = (i: number) => pages.find((p) => p.debut === i)!;
    expect(seule(2)).toMatchObject({ gabarit: "seule", couvrir: true }); // 16:9
    expect(seule(4)).toMatchObject({ gabarit: "seule", couvrir: false }); // 4:3 : entière sur son flou
    expect(seule(3)).toMatchObject({ gabarit: "seule", couvrir: false }); // portrait sans voisin portrait
  });

  it("les cases remplissent l'écran exactement", () => {
    for (const p of pages) expect(p.cases.reduce((a, c) => a + c.l * c.h, 0)).toBeCloseTo(1, 9);
  });
});
