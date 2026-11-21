"""Couleurs vives tirées des photos, et palettes lisibles pour le site.

Deux temps :

1. Par média, à la génération des rendus (ou par `calculer_couleurs` depuis la
   miniature en cache) : `couleurs_vives(image)` garde jusqu'à 5 couleurs
   franches avec leur part dans l'image. La « couleur dominante » (`couleur`)
   reste la couleur la plus présente, souvent grise : elle sert au
   placeholder, pas à l'ambiance.

2. Par voyage ou par jour, à chaque appel d'API : `palette(medias)` regroupe
   les couleurs des médias par teinte et en tire un accent, un fond teinté et
   un dégradé. Les contrastes WCAG AA (4,5:1) sont garantis ici, une fois :
   le front applique les couleurs sans rien recalculer.

Les calculs se font en OKLCH (luminosité, chroma, teinte perçues), où
« assombrir sans changer de teinte » a un sens, contrairement au RGB ou au HSL.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from PIL import Image

# --- Conversions sRGB ↔ OKLab ↔ OKLCH (Björn Ottosson) -----------------------


def _lineaire(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_vers_rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_vers_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{round(min(255, max(0, c))):02x}" for c in rgb)


def rgb_vers_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_lineaire(c / 255) for c in rgb)
    l_ = math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m_ = math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s_ = math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _oklab_vers_rgb_lineaire(lab: tuple[float, float, float]) -> tuple[float, float, float]:
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


@dataclass(frozen=True)
class Oklch:
    L: float  # 0 (noir) → 1 (blanc)
    C: float  # 0 (gris) → ~0,37
    h: float  # degrés

    @classmethod
    def depuis_hex(cls, hex_: str) -> Oklch:
        L, a, b = rgb_vers_oklab(hex_vers_rgb(hex_))
        return cls(L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360)

    def _lineaire(self):
        h = math.radians(self.h)
        return _oklab_vers_rgb_lineaire((self.L, self.C * math.cos(h), self.C * math.sin(h)))

    def dans_le_gamut(self) -> bool:
        return all(-1e-4 <= c <= 1 + 1e-4 for c in self._lineaire())

    def ramener(self) -> Oklch:
        """Même luminosité et même teinte, chroma réduit jusqu'à tenir en sRGB."""
        if self.dans_le_gamut():
            return self
        bas, haut = 0.0, self.C
        for _ in range(20):
            milieu = (bas + haut) / 2
            if Oklch(self.L, milieu, self.h).dans_le_gamut():
                bas = milieu
            else:
                haut = milieu
        return Oklch(self.L, bas, self.h)

    def hex(self) -> str:
        return rgb_vers_hex(tuple(_gamma(min(1, max(0, c))) * 255 for c in self.ramener()._lineaire()))


# --- Contraste WCAG -----------------------------------------------------------


def luminance(hex_: str) -> float:
    r, g, b = (_lineaire(c / 255) for c in hex_vers_rgb(hex_))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


AA = 4.5
ENCRE = "#1d1b18"  # mêmes valeurs que --encre, --encre-2, --encre-3 (tokens.css)
ENCRE_2 = "#5d5850"
ENCRE_3 = "#68625a"
TEXTES_NEUTRES = [ENCRE, ENCRE_2, ENCRE_3]
BLANC = "#ffffff"

# --- 1. Couleurs vives d'une image -------------------------------------------

CHROMA_MIN = 0.05  # en dessous : gris, beige délavé, ciel blanc
L_MIN, L_MAX = 0.25, 0.93  # ni ombres, ni hautes lumières


def couleurs_vives(image: Image.Image, nombre: int = 5) -> list[dict]:
    """Jusqu'à `nombre` couleurs franches de l'image, la plus marquante d'abord :
    [{"hex": "#c2185b", "part": 0.12}, …] (`part` = fraction de l'image).

    Réduction à 12 couleurs d'une vignette de 64 px, puis tri par
    part × chroma : une petite tache très colorée (un torii) l'emporte sur un
    grand aplat terne (un mur gris). Liste vide pour une image sans couleur.
    """
    petite = image.convert("RGB")
    petite.thumbnail((64, 64), Image.Resampling.BILINEAR)
    quantifiee = petite.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    total = petite.width * petite.height
    valeurs = quantifiee.getpalette()
    candidates = []
    for nb, indice in quantifiee.getcolors() or []:
        hex_ = rgb_vers_hex(tuple(valeurs[3 * indice: 3 * indice + 3]))
        c = Oklch.depuis_hex(hex_)
        if c.C < CHROMA_MIN or not (L_MIN <= c.L <= L_MAX):
            continue
        part = nb / total
        candidates.append((part * c.C, hex_, part))
    candidates.sort(reverse=True)
    return [{"hex": hex_, "part": round(part, 4)} for _, hex_, part in candidates[:nombre]]


# --- 2. Palette d'un voyage ou d'un jour --------------------------------------

NB_CASES = 24  # cases de teinte de 15°
TEINTE_PAR_DEFAUT = 45.0  # terre cuite, comme la palette provisoire
ECART_DEGRADE = 40.0  # degrés minimum entre deux couleurs du dégradé


def _vif(c: Oklch, *, l_min=0.62, l_max=0.75, c_min=0.13) -> Oklch:
    """Version franche d'une couleur : luminosité moyenne, chroma minimum."""
    return Oklch(min(l_max, max(l_min, c.L)), max(c_min, c.C), c.h).ramener()


def _ajuster(couleur: Oklch, fonds: list[str], sens: int) -> Oklch:
    """Assombrit (sens -1) ou éclaircit (+1) jusqu'au contraste AA sur tous les fonds."""
    c = couleur
    while not all(contraste(c.hex(), f) >= AA for f in fonds):
        L = c.L + 0.01 * sens
        if not 0 <= L <= 1:
            break
        c = Oklch(L, c.C, c.h).ramener()
    return c


def _ecart(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def palette(medias: Iterable[tuple[list[dict], float]]) -> dict:
    """Palette à partir des couleurs vives de médias, chacun avec un poids
    (couverture, favori). Toujours une palette complète, même sans couleur.

    - `accent` : la teinte la plus marquante, franche (surfaces, filets) ;
    - `accent_texte` : la même, assez foncée pour du texte sur `fond` et `fond_2` ;
    - `sur_accent` : blanc ou encre, lisible sur `accent` ;
    - `fond`, `fond_2` : papier teinté de l'accent ;
    - `degrade` : 2 ou 3 teintes distinctes du voyage ou du jour ;
    - `halos` : 3 teintes pastel pour les halos du fond, assez claires pour
      que tout le texte (encres et `accent_texte`) y reste AA.
    """
    cases = [[0.0, 0.0, 0.0, 0.0] for _ in range(NB_CASES)]  # poids, ΣL, Σa, Σb (pondérés)
    for couleurs, poids in medias:
        for entree in couleurs or []:
            c = Oklch.depuis_hex(entree["hex"])
            w = entree["part"] * c.C * poids
            if w <= 0:
                continue
            case = cases[int(c.h // (360 / NB_CASES)) % NB_CASES]
            h = math.radians(c.h)
            case[0] += w
            case[1] += w * c.L
            case[2] += w * c.C * math.cos(h)
            case[3] += w * c.C * math.sin(h)

    # Lissage : une teinte à cheval sur deux cases n'est pas coupée en deux.
    scores = [
        cases[i][0] + 0.5 * (cases[i - 1][0] + cases[(i + 1) % NB_CASES][0]) for i in range(NB_CASES)
    ]
    teintes: list[Oklch] = []
    for i in sorted(range(NB_CASES), key=lambda i: -scores[i]):
        poids, sL, sa, sb = cases[i]
        if poids <= 0:
            continue
        c = Oklch(sL / poids, math.hypot(sa, sb) / poids, math.degrees(math.atan2(sb, sa)) % 360)
        if all(_ecart(c.h, t.h) >= ECART_DEGRADE for t in teintes):
            teintes.append(c)
        if len(teintes) == 3:
            break

    if not teintes:
        teintes = [Oklch(0.6, 0.12, TEINTE_PAR_DEFAUT)]
    base = _vif(teintes[0])
    h = base.h

    fond = Oklch(0.975, min(0.018, base.C * 0.15), h).hex()
    fond_2 = Oklch(0.945, min(0.035, base.C * 0.28), h).hex()
    accent_texte = _ajuster(Oklch(min(base.L, 0.55), base.C, h).ramener(), [fond, fond_2], -1)

    # Texte sur l'accent : blanc (accent assombri si besoin) ou encre (accent
    # éclairci si besoin), selon ce qui dénature le moins la couleur. Un orange
    # ou un vert restent ainsi éclatants sous l'encre au lieu de virer au brun.
    sous_blanc = _ajuster(base, [BLANC], -1)
    sous_encre = _ajuster(base, [ENCRE], +1)
    if abs(sous_blanc.L - base.L) <= abs(sous_encre.L - base.L):
        sur_accent, accent = BLANC, sous_blanc
    else:
        sur_accent, accent = ENCRE, sous_encre

    degrade = [_vif(t, l_min=0.62, l_max=0.8).hex() for t in teintes]
    if len(degrade) == 1:
        # Une seule teinte : dégradé de l'accent vers une version plus claire.
        degrade.append(_vif(Oklch(base.L + 0.15, base.C * 0.8, (h + 25) % 360), l_max=0.85).hex())

    # Halos : les teintes du voyage en pastel ; s'il en manque, des voisines de
    # l'accent (±40°) pour garder trois couleurs.
    sources = teintes + [Oklch(base.L, base.C, (h + d) % 360) for d in (40, -40)]
    halos = [
        _ajuster(Oklch(0.9, min(0.11, max(0.07, t.C)), t.h).ramener(), [accent_texte.hex(), *TEXTES_NEUTRES], +1).hex()
        for t in sources[:3]
    ]

    return {
        "accent": accent.hex(),
        "accent_texte": accent_texte.hex(),
        "sur_accent": sur_accent,
        "fond": fond,
        "fond_2": fond_2,
        "degrade": degrade,
        "halos": halos,
    }


def poids_media(*, favori: bool, couverture: bool) -> float:
    """La couverture compte triple, un favori double."""
    return 3.0 if couverture else 2.0 if favori else 1.0
