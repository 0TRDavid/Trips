"""Sidecars XMP des valeurs saisies à la main (date, position).

Un fichier `<nom.ext>.xmp` par média qui a au moins une valeur « manuel »,
dans le dossier d'export Nextcloud, en miroir du dossier du voyage :

    Shared/Métadonnées/Japon 2025/xmp/Whatsapp/IMG-20250604-WA0000.jpg.xmp

Nommage `nom.ext.xmp` (darktable, digiKam) : `IMG_1.HEIC` et `IMG_1.MOV` ne se
marchent pas dessus. Champs standard lus par exiftool et les logiciels photo
(exif:DateTimeOriginal, photoshop:DateCreated, exif:GPS*), plus `carnet:` qui
dit d'où vient chaque valeur. Seules les valeurs manuelles y figurent : le
reste est déjà dans l'original. Pas de date de génération dans le fichier :
même saisie = même fichier (on ne réécrit que ce qui change).
"""

from __future__ import annotations

import hashlib
import posixpath
from xml.sax.saxutils import quoteattr
from zoneinfo import ZoneInfo

from .models import Photo, Source
from .nextcloud import normaliser

NS_CARNET = "http://ns.carnet-de-voyages.local/1.0/"
SOUS_DOSSIER = "xmp"


def _gps(valeur: float, positif: str, negatif: str) -> str:
    """35.6586 → « 35,39.516000N » (format XMP : degrés, minutes décimales, sens)."""
    sens = positif if valeur >= 0 else negatif
    valeur = abs(valeur)
    degres = int(valeur)
    minutes = (valeur - degres) * 60
    return f"{degres},{minutes:.6f}{sens}"


def a_exporter(photo: Photo) -> bool:
    return Source.MANUEL in (photo.source_date, photo.source_position)


def contenu_xmp(photo: Photo, fuseau: str) -> bytes | None:
    """Le sidecar d'un média, ou None s'il n'a aucune valeur saisie à la main."""
    if not a_exporter(photo):
        return None
    attributs: list[tuple[str, str]] = []
    if photo.source_date == Source.MANUEL:
        locale = photo.prise_le.astimezone(ZoneInfo(fuseau)).isoformat(timespec="seconds")
        attributs += [
            ("exif:DateTimeOriginal", locale),
            ("photoshop:DateCreated", locale),
            ("carnet:SourceDate", "manuel"),
        ]
    if photo.source_position == Source.MANUEL and photo.latitude is not None and photo.longitude is not None:
        attributs += [
            ("exif:GPSVersionID", "2.3.0.0"),
            ("exif:GPSLatitude", _gps(photo.latitude, "N", "S")),
            ("exif:GPSLongitude", _gps(photo.longitude, "E", "W")),
        ]
        if photo.altitude is not None:
            attributs += [
                ("exif:GPSAltitudeRef", "1" if photo.altitude < 0 else "0"),
                ("exif:GPSAltitude", f"{round(abs(photo.altitude) * 100)}/100"),
            ]
        attributs.append(("carnet:SourcePosition", "manuel"))
    lignes = "\n".join(f"    {nom}={quoteattr(valeur)}" for nom, valeur in attributs)
    texte = f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Carnet de voyages">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:exif="http://ns.adobe.com/exif/1.0/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmlns:carnet="{NS_CARNET}"
{lignes}/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""
    return texte.encode("utf-8")


def chemin_xmp(photo: Photo, dossier_voyage: str, dossier_export: str) -> str:
    """Chemin du sidecar : dossier d'export / nom du voyage / xmp / chemin relatif + .xmp."""
    dossier_voyage = normaliser(dossier_voyage)
    chemin = normaliser(photo.chemin_nextcloud)
    relatif = chemin[len(dossier_voyage) + 1:] if chemin.startswith(dossier_voyage + "/") else posixpath.basename(chemin)
    return f"{normaliser(dossier_export)}/{posixpath.basename(dossier_voyage)}/{SOUS_DOSSIER}/{relatif}.xmp"


def empreinte(chemin: str, contenu: bytes) -> str:
    """Change si le contenu ou l'emplacement change (média déplacé dans Nextcloud)."""
    return hashlib.sha256(chemin.encode() + b"\0" + contenu).hexdigest()
