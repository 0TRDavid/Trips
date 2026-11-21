"""Rendus web d'une photo : WebP en trois tailles, sans aucune métadonnée.

Ce module ne touche pas à la base : il reçoit les octets de l'original (en
mémoire, jamais écrits sur disque) et écrit les rendus dans le cache. Il peut
donc tourner dans un processus séparé.

Ce qui garantit l'absence de métadonnées (GPS, EXIF, XMP, profil ICC) :
- les pixels sont recopiés dans une image neuve, sans `info` hérité ;
- Pillow n'écrit EXIF, XMP ou ICC dans un WebP que si on les lui passe, ce
  qu'on ne fait jamais.
"""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass, field
from pathlib import Path

import pillow_heif
from PIL import Image, ImageCms, ImageOps

from .palette import couleurs_vives
from .thumbhash import thumbhash_image

pillow_heif.register_heif_opener()

# Côté le plus long, en pixels.
TAILLES = {"miniature": 400, "moyenne": 1280, "grande": 2560}
QUALITE = {"miniature": 75, "moyenne": 80, "grande": 82}
FORMAT = "webp"

_SRGB = ImageCms.createProfile("sRGB")


@dataclass
class FichierRendu:
    taille: str
    fichier: str  # relatif à la racine du cache
    largeur: int
    hauteur: int
    octets: int


@dataclass
class ResultatRendu:
    largeur: int  # dimensions de l'original, orientation appliquée
    hauteur: int
    couleur: str  # « #rrggbb »
    placeholder: str  # ThumbHash en base64
    couleurs: list[dict] = field(default_factory=list)  # couleurs vives (palette.py)
    fichiers: list[FichierRendu] = field(default_factory=list)


def prefixe_fichiers(photo_id: int, etag: str) -> str:
    """« rendus/42/3f9a…-» : l'etag dans le nom rend l'URL immuable."""
    empreinte = hashlib.sha1(etag.encode()).hexdigest()[:10]
    return f"rendus/{photo_id}/{empreinte}"


def decoder(octets: bytes) -> Image.Image:
    """Ouvre l'original, applique l'orientation et convertit en sRGB 8 bits.

    Renvoie une image neuve qui ne porte que des pixels (aucune métadonnée).
    Un CR2 est lu comme un TIFF : Pillow décode le JPEG pleine taille qu'il
    embarque.
    """
    with Image.open(io.BytesIO(octets)) as image:
        if image.format == "JPEG":
            # Décodage directement à échelle réduite quand c'est possible (plus rapide).
            image.draft("RGB", (max(TAILLES.values()),) * 2)
        icc = image.info.get("icc_profile")
        # JPEG et CR2 : rotation EXIF. HEIC : libheif l'a déjà appliquée (EXIF à 1).
        image = ImageOps.exif_transpose(image)
    image = _vers_srgb(image, icc)
    return Image.frombytes("RGB", image.size, image.tobytes())


def _vers_srgb(image: Image.Image, icc: bytes | None) -> Image.Image:
    if icc and image.mode in ("RGB", "CMYK"):
        try:
            source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            return ImageCms.profileToProfile(
                image, source, _SRGB,
                renderingIntent=ImageCms.Intent.PERCEPTUAL, outputMode="RGB",
            )
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass  # profil illisible : on garde les valeurs telles quelles
    return image.convert("RGB")


def dimensions_cibles(largeur: int, hauteur: int, cote_max: int) -> tuple[int, int]:
    """Réduit pour que le côté le plus long fasse `cote_max`, sans jamais agrandir."""
    cote = max(largeur, hauteur)
    if cote <= cote_max:
        return largeur, hauteur
    facteur = cote_max / cote
    return max(1, round(largeur * facteur)), max(1, round(hauteur * facteur))


def couleur_dominante(image: Image.Image) -> str:
    """Couleur la plus présente, après réduction à 5 couleurs d'une vignette de 64 px."""
    petite = image.copy()
    petite.thumbnail((64, 64), Image.Resampling.BILINEAR)
    palette = petite.quantize(colors=5, method=Image.Quantize.MEDIANCUT)
    _, indice = max(palette.getcolors())
    r, g, b = palette.getpalette()[3 * indice: 3 * indice + 3]
    return f"#{r:02x}{g:02x}{b:02x}"


# Rotation manuelle (degrés, sens horaire) → transposition sans perte.
_TRANSPOSITIONS = {
    90: Image.Transpose.ROTATE_270,  # Pillow tourne dans le sens trigonométrique
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}


def tourner(image: Image.Image, rotation: int) -> Image.Image:
    """Applique la rotation manuelle d'un média (0, 90, 180, 270 ; sens horaire)."""
    if rotation % 360 == 0:
        return image
    return image.transpose(_TRANSPOSITIONS[rotation % 360])


def produire_rendus(octets: bytes, racine: Path, prefixe: str, rotation: int = 0) -> ResultatRendu:
    """Écrit les trois rendus `<racine>/<prefixe>-<taille>.webp` et renvoie leurs infos.

    `rotation` : correction manuelle, appliquée après l'orientation EXIF."""
    image = tourner(decoder(octets), rotation)
    resultat = ResultatRendu(
        largeur=image.width,
        hauteur=image.height,
        couleur=couleur_dominante(image),
        placeholder=thumbhash_image(image),
        couleurs=couleurs_vives(image),
    )
    (racine / prefixe).parent.mkdir(parents=True, exist_ok=True)

    # Du plus grand au plus petit : chaque taille est réduite depuis la précédente
    # (plus rapide), mais ses dimensions sont calculées depuis l'original (sinon
    # les arrondis successifs déforment le ratio).
    source = image
    for taille, cote_max in sorted(TAILLES.items(), key=lambda t: -t[1]):
        dimensions = dimensions_cibles(image.width, image.height, cote_max)
        if dimensions != source.size:
            source = source.resize(dimensions, Image.Resampling.LANCZOS, reducing_gap=3.0)
        relatif = f"{prefixe}-{taille}.{FORMAT}"
        octets_ecrits = _ecrire_webp(source, racine / relatif, QUALITE[taille])
        resultat.fichiers.append(FichierRendu(taille, relatif, source.width, source.height, octets_ecrits))
    return resultat


def _ecrire_webp(image: Image.Image, chemin: Path, qualite: int) -> int:
    """Écriture atomique : un rendu à moitié écrit n'est jamais visible."""
    tampon = io.BytesIO()
    # Ni exif, ni xmp, ni icc_profile : le fichier ne contient que l'image.
    image.save(tampon, format="WEBP", quality=qualite, method=4)
    temporaire = chemin.with_name(chemin.name + ".tmp")
    temporaire.write_bytes(tampon.getvalue())
    os.replace(temporaire, chemin)
    return len(tampon.getvalue())
