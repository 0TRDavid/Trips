"""Extraction des métadonnées EXIF (JPEG et HEIC) depuis des octets en mémoire.

Pillow lit l'en-tête sans décoder l'image : l'extraction reste rapide, même
pour un HEIC de plusieurs Mo.

Orientation : c'est la rotation qu'il reste à appliquer à l'image *décodée*.
Pour un HEIC, libheif applique déjà la rotation et pillow-heif remet l'EXIF à 1 ;
pour un JPEG, c'est la valeur EXIF d'origine.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo

import pillow_heif
from PIL import ExifTags, Image, UnidentifiedImageError

pillow_heif.register_heif_opener()

# Balises EXIF utilisées (numéros standard).
MAKE, MODEL, ORIENTATION, DATETIME = 0x010F, 0x0110, 0x0112, 0x0132
DATETIME_ORIGINAL, DATETIME_DIGITIZED = 0x9003, 0x9004
OFFSET_TIME, OFFSET_TIME_ORIGINAL, OFFSET_TIME_DIGITIZED = 0x9010, 0x9011, 0x9012
GPS_LAT_REF, GPS_LAT, GPS_LON_REF, GPS_LON, GPS_ALT_REF, GPS_ALT = 1, 2, 3, 4, 5, 6


@dataclass
class Metadonnees:
    prise_le: datetime | None = None  # UTC, timezone-aware
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    appareil: str = ""
    orientation: int | None = None


def extraire_metadonnees(
    contenu: bytes, fuseau: tzinfo, horloges: dict[str, tzinfo] | None = None
) -> Metadonnees:
    """Lit les EXIF d'une image. Ne lève jamais d'erreur sur des EXIF absents ou abîmés.

    Une date sans décalage horaire explicite est lue dans l'horloge de son
    appareil (`horloges`, par nom d'appareil) ou, à défaut, dans `fuseau`.
    """
    try:
        with Image.open(io.BytesIO(contenu)) as image:
            exif = image.getexif()
    except (UnidentifiedImageError, OSError, ValueError):
        return Metadonnees()

    ifd_exif = _ifd(exif, ExifTags.IFD.Exif)
    ifd_gps = _ifd(exif, ExifTags.IFD.GPSInfo)
    latitude, longitude = _coordonnees(ifd_gps)
    appareil = _appareil(exif.get(MAKE), exif.get(MODEL))
    horloge = (horloges or {}).get(appareil, fuseau)
    return Metadonnees(
        prise_le=_date_prise(exif, ifd_exif, horloge),
        latitude=latitude,
        longitude=longitude,
        altitude=_altitude(ifd_gps),
        appareil=appareil,
        orientation=_orientation(exif.get(ORIENTATION)),
    )


def _ifd(exif: Image.Exif, cle) -> dict:
    try:
        return dict(exif.get_ifd(cle))
    except (KeyError, ValueError, TypeError, OSError):
        return {}


# --- Date ---------------------------------------------------------------

def _date_prise(exif, ifd_exif, fuseau: tzinfo) -> datetime | None:
    # Par ordre de préférence : prise de vue, numérisation, modification.
    candidats = [
        (ifd_exif.get(DATETIME_ORIGINAL), ifd_exif.get(OFFSET_TIME_ORIGINAL)),
        (ifd_exif.get(DATETIME_DIGITIZED), ifd_exif.get(OFFSET_TIME_DIGITIZED)),
        (exif.get(DATETIME), ifd_exif.get(OFFSET_TIME)),
    ]
    for valeur, decalage in candidats:
        locale = _analyser_date(valeur)
        if locale is None:
            continue
        tz = analyser_decalage(decalage) or fuseau
        return locale.replace(tzinfo=tz).astimezone(timezone.utc)
    return None


def _texte(valeur) -> str:
    if isinstance(valeur, bytes):
        valeur = valeur.decode("ascii", errors="ignore")
    return str(valeur or "").strip("\x00 ").strip()


def _analyser_date(valeur) -> datetime | None:
    texte = _texte(valeur)
    try:
        return datetime.strptime(texte[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


_DECALAGE = re.compile(r"^([+-])(\d{2}):?(\d{2})$")


def analyser_decalage(valeur) -> timezone | None:
    correspondance = _DECALAGE.match(_texte(valeur))
    if not correspondance:
        return None
    signe, heures, minutes = correspondance.groups()
    delta = timedelta(hours=int(heures), minutes=int(minutes))
    return timezone(-delta if signe == "-" else delta)


# --- GPS ------------------------------------------------------------------

def _nombre(valeur) -> float | None:
    try:
        nombre = float(valeur)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return nombre if math.isfinite(nombre) else None


def _degres(valeur, reference, negatif: str) -> float | None:
    try:
        d, m, s = (_nombre(v) for v in valeur)
    except (TypeError, ValueError):
        return None
    if None in (d, m, s):
        return None
    decimal = d + m / 60 + s / 3600
    return -decimal if _texte(reference).upper() == negatif else decimal


def _coordonnees(gps: dict) -> tuple[float | None, float | None]:
    latitude = _degres(gps.get(GPS_LAT), gps.get(GPS_LAT_REF), "S")
    longitude = _degres(gps.get(GPS_LON), gps.get(GPS_LON_REF), "W")
    if latitude is None or longitude is None:
        return None, None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None, None
    return round(latitude, 7), round(longitude, 7)


def _altitude(gps: dict) -> float | None:
    altitude = _nombre(gps.get(GPS_ALT))
    if altitude is None:
        return None
    reference = gps.get(GPS_ALT_REF)
    if isinstance(reference, bytes):
        reference = reference[:1] == b"\x01"
    sous_la_mer = reference in (1, True)
    return round(-altitude if sous_la_mer else altitude, 2)


# --- Appareil et orientation ---------------------------------------------

def _appareil(marque, modele) -> str:
    marque, modele = _texte(marque), _texte(modele)
    if marque and modele.lower().startswith(marque.lower()):
        return modele
    return " ".join(p for p in (marque, modele) if p)


def _orientation(valeur) -> int | None:
    try:
        valeur = int(valeur)
    except (TypeError, ValueError):
        return None
    return valeur if 1 <= valeur <= 8 else None
