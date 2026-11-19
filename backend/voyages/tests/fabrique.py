"""Images de test générées en mémoire, avec de faux EXIF (aucune vraie photo dans le dépôt)."""

import io

import pillow_heif
from PIL import ExifTags, Image
from PIL.TiffImagePlugin import IFDRational

pillow_heif.register_heif_opener()


def _dms(valeur: float):
    valeur = abs(valeur)
    degres = int(valeur)
    minutes = int((valeur - degres) * 60)
    secondes = round(((valeur - degres) * 60 - minutes) * 60 * 10000)
    return (IFDRational(degres, 1), IFDRational(minutes, 1), IFDRational(secondes, 10000))


def image(
    format="JPEG",
    *,
    date="2025:04:05 14:30:00",
    decalage=None,
    lat=None,
    lon=None,
    altitude=None,
    gps=None,
    marque="Apple",
    modele="iPhone 15 Pro",
    orientation=6,
    sans_exif=False,
) -> bytes:
    """Renvoie les octets d'une petite image JPEG ou HEIC.

    `gps` permet de fournir un dictionnaire GPS brut (pour les cas abîmés).
    """
    img = Image.new("RGB", (16, 16), (200, 80, 40))
    tampon = io.BytesIO()
    if sans_exif:
        img.save(tampon, format=format)
        return tampon.getvalue()

    exif = Image.Exif()
    if marque:
        exif[0x010F] = marque
    if modele:
        exif[0x0110] = modele
    if orientation:
        exif[0x0112] = orientation
    ifd_exif = exif.get_ifd(ExifTags.IFD.Exif)
    if date:
        ifd_exif[0x9003] = date
    if decalage:
        ifd_exif[0x9011] = decalage

    if gps is not None:
        exif.get_ifd(ExifTags.IFD.GPSInfo).update(gps)
    elif lat is not None:
        ifd_gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        ifd_gps[1] = "N" if lat >= 0 else "S"
        ifd_gps[2] = _dms(lat)
        ifd_gps[3] = "E" if lon >= 0 else "W"
        ifd_gps[4] = _dms(lon)
        if altitude is not None:
            ifd_gps[5] = b"\x01" if altitude < 0 else b"\x00"
            ifd_gps[6] = IFDRational(round(abs(altitude) * 100), 100)

    img.save(tampon, format=format, exif=exif.tobytes())
    return tampon.getvalue()
