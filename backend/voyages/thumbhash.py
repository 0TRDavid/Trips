"""ThumbHash : un aperçu flou de l'image en ~25 octets.

Portage en Python de l'encodeur de référence d'Evan Wallace
(https://github.com/evanw/thumbhash, licence MIT), limité aux images opaques
(les rendus sont toujours en RGB). Le front le décode avec le paquet npm
`thumbhash` (`thumbHashToDataURL`).

Le paquet PyPI `thumbhash-python` exige Pillow < 11, d'où ce portage.
"""

from __future__ import annotations

import base64
import math

from PIL import Image

TAILLE_MAX = 100  # l'algorithme travaille sur une image de 100 px au plus


def _arrondi(x: float) -> int:
    # Math.round de JavaScript (moitié vers le haut), pas l'arrondi bancaire de Python.
    return math.floor(x + 0.5)


def thumbhash_rgb(largeur: int, hauteur: int, rgb: bytes) -> bytes:
    """Encode des pixels RGB (3 octets par pixel, 100×100 au plus)."""
    if largeur > TAILLE_MAX or hauteur > TAILLE_MAX:
        raise ValueError(f"{largeur}×{hauteur} dépasse {TAILLE_MAX}×{TAILLE_MAX}")
    n = largeur * hauteur
    # Luminance (l), et deux axes de chrominance (p : jaune-bleu, q : rouge-vert).
    l, p, q = [0.0] * n, [0.0] * n, [0.0] * n
    for i in range(n):
        r, g, b = rgb[3 * i] / 255, rgb[3 * i + 1] / 255, rgb[3 * i + 2] / 255
        l[i] = (r + g + b) / 3
        p[i] = (r + g) / 2 - b
        q[i] = r - g

    def encoder_canal(canal, nx, ny):
        dc, ac, echelle = 0.0, [], 0.0
        for cy in range(ny):
            fy = [math.cos(math.pi / hauteur * cy * (y + 0.5)) for y in range(hauteur)]
            cx = 0
            while cx * ny < nx * (ny - cy):
                fx = [math.cos(math.pi / largeur * cx * (x + 0.5)) for x in range(largeur)]
                f = 0.0
                for y in range(hauteur):
                    ligne, facteur_y = y * largeur, fy[y]
                    for x in range(largeur):
                        f += canal[ligne + x] * fx[x] * facteur_y
                f /= n
                if cx or cy:
                    ac.append(f)
                    echelle = max(echelle, abs(f))
                else:
                    dc = f
                cx += 1
        if echelle:
            ac = [0.5 + 0.5 / echelle * f for f in ac]
        return dc, ac, echelle

    limite_l = 7  # 5 pour une image avec transparence, non gérée ici
    lx = max(1, _arrondi(limite_l * largeur / max(largeur, hauteur)))
    ly = max(1, _arrondi(limite_l * hauteur / max(largeur, hauteur)))
    l_dc, l_ac, l_echelle = encoder_canal(l, max(3, lx), max(3, ly))
    p_dc, p_ac, p_echelle = encoder_canal(p, 3, 3)
    q_dc, q_ac, q_echelle = encoder_canal(q, 3, 3)

    paysage = largeur > hauteur
    entete24 = (
        _arrondi(63 * l_dc)
        | (_arrondi(31.5 + 31.5 * p_dc) << 6)
        | (_arrondi(31.5 + 31.5 * q_dc) << 12)
        | (_arrondi(31 * l_echelle) << 18)
    )
    entete16 = (
        (ly if paysage else lx)
        | (_arrondi(63 * p_echelle) << 3)
        | (_arrondi(63 * q_echelle) << 9)
        | (int(paysage) << 15)
    )
    resultat = [entete24 & 255, (entete24 >> 8) & 255, entete24 >> 16, entete16 & 255, entete16 >> 8]
    # Coefficients AC sur 4 bits, deux par octet.
    for indice, f in enumerate(l_ac + p_ac + q_ac):
        position = 5 + (indice >> 1)
        if position == len(resultat):
            resultat.append(0)
        resultat[position] |= _arrondi(15 * f) << ((indice & 1) << 2)
    return bytes(resultat)


def thumbhash_image(image: Image.Image) -> str:
    """ThumbHash en base64 d'une image Pillow (réduite à 100 px au plus)."""
    petite = image.convert("RGB")
    petite.thumbnail((TAILLE_MAX, TAILLE_MAX), Image.Resampling.BILINEAR)
    return base64.b64encode(thumbhash_rgb(petite.width, petite.height, petite.tobytes())).decode("ascii")


# --- Lecture (utilisée par les tests, et utile pour vérifier une valeur en base) ---

def ratio_approximatif(hash_: bytes) -> float:
    """Rapport largeur / hauteur approximatif encodé dans le hash."""
    a_transparence = hash_[2] & 0x80
    paysage = hash_[4] & 0x80
    lx = (5 if a_transparence else 7) if paysage else hash_[3] & 7
    ly = hash_[3] & 7 if paysage else (5 if a_transparence else 7)
    return lx / ly


def couleur_moyenne(hash_: bytes) -> tuple[float, float, float]:
    """Couleur moyenne (r, g, b) entre 0 et 1."""
    entete = hash_[0] | (hash_[1] << 8) | (hash_[2] << 16)
    l = (entete & 63) / 63
    p = ((entete >> 6) & 63) / 31.5 - 1
    q = ((entete >> 12) & 63) / 31.5 - 1
    b = l - 2 / 3 * p
    r = (3 * l - b + q) / 2
    g = r - q
    return tuple(max(0.0, min(1.0, c)) for c in (r, g, b))
