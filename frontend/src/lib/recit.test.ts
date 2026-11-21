import { describe, expect, it } from "vitest";
import { bornesHeures, entremeler } from "./recit";

const p = (id: number, hhmm: string | null) => ({ id, prise_le: hhmm ? `2025-06-05T${hhmm}:00+09:00` : null });
const photos = [p(1, "09:10"), p(2, "09:40"), p(3, "14:05"), p(4, "14:45"), p(5, "18:00")];
const ids = (seg: { genre: string; photos?: { id: number }[] }) => seg.photos?.map((x) => x.id);

describe("entremeler", () => {
  it("sans récit : un moment par heure, comme avant", () => {
    const e = entremeler(photos, []);
    expect(e.map((x) => (x.genre === "moment" ? x.heure : "r"))).toEqual([9, 14, 18]);
  });

  it("texte sans heure en tête, texte à l'heure pile avant l'intitulé", () => {
    const e = entremeler(photos, [
      { heure: null, html: "intro" },
      { heure: "14:00", html: "aprem" },
    ]);
    expect(e.map((x) => (x.genre === "recit" ? x.html : x.heure))).toEqual(["intro", 9, "aprem", 14, 18]);
  });

  it("texte au milieu d'une heure : coupe les rangées sous le même intitulé", () => {
    const e = entremeler(photos, [{ heure: "14:30", html: "marché" }]);
    const quatorze = e[1];
    expect(quatorze.genre === "moment" && quatorze.segments.map((s) => (s.genre === "recit" ? s.html : ids(s)))).toEqual([
      [3],
      "marché",
      [4],
    ]);
  });

  it("texte plus tard que toutes les photos : à la fin ; ordre d'écriture conservé", () => {
    const e = entremeler(photos, [
      { heure: "23:00", html: "a" },
      { heure: "23:30", html: "b" },
    ]);
    expect(e.slice(-2)).toEqual([
      { genre: "recit", html: "a" },
      { genre: "recit", html: "b" },
    ]);
  });

  it("ignore les photos sans heure pour placer, suit l'ordre de l'API", () => {
    const e = entremeler([p(1, null), p(2, "10:00"), p(3, "08:00")], [{ heure: "09:00", html: "x" }]);
    expect(e.map((x) => (x.genre === "recit" ? x.html : x.heure))).toEqual([null, "x", 10, 8]);
  });

  it("toutes les photos restent présentes, une seule fois", () => {
    const e = entremeler(photos, [{ heure: "09:30", html: "a" }, { heure: "14:30", html: "b" }]);
    const vues = e.flatMap((x) => (x.genre === "moment" ? x.segments.flatMap((s) => ids(s) ?? []) : []));
    expect(vues).toEqual([1, 2, 3, 4, 5]);
  });
});

describe("bornesHeures", () => {
  it("première et dernière heure datées", () => {
    expect(bornesHeures([p(1, "14:00"), p(2, null), p(3, "07:59"), p(4, "21:10")])).toEqual([7, 21]);
    expect(bornesHeures([p(1, null)])).toBeNull();
  });
});

describe("plusProcheDuCentre", () => {
  it("élit la boîte dont le centre est le plus proche", async () => {
    const { plusProcheDuCentre } = await import("./lecture");
    expect(plusProcheDuCentre([], 400)).toBe(-1);
    expect(
      plusProcheDuCentre(
        [
          { top: -100, bottom: 200 },
          { top: 300, bottom: 520 },
          { top: 600, bottom: 900 },
        ],
        422,
      ),
    ).toBe(1);
  });
});
