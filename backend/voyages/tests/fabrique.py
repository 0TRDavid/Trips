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


# --- Rendus -------------------------------------------------------------------

import struct
import tempfile

from django.test import override_settings

ROUGE, BLEU = (230, 20, 20), (20, 20, 230)

XMP = (
    b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>'
    b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    b'<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:GPSLatitude="35,0.0N"/>'
    b"</rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
)


def _s15f16(*valeurs):
    return b"".join(struct.pack(">i", round(v * 65536)) for v in valeurs)


def profil_display_p3() -> bytes:
    """Profil ICC v2 minimal « Display P3 » (primaires adaptées D50, gamma 2,2).

    Assez fidèle pour vérifier qu'une conversion vers sRGB a bien lieu.
    """
    def xyz(x, y, z):
        return b"XYZ \0\0\0\0" + _s15f16(x, y, z)

    courbe = b"curv\0\0\0\0" + struct.pack(">IH", 1, round(2.2 * 256)) + b"\0\0"
    texte = b"Display P3 (test)\0"
    desc = b"desc\0\0\0\0" + struct.pack(">I", len(texte)) + texte + b"\0" * (4 + 4 + 2 + 1 + 67)
    balises = [
        (b"desc", desc),
        (b"wtpt", xyz(0.9642, 1.0, 0.8249)),
        (b"rXYZ", xyz(0.5151, 0.2412, -0.0011)),
        (b"gXYZ", xyz(0.2920, 0.6922, 0.0419)),
        (b"bXYZ", xyz(0.1571, 0.0666, 0.7841)),
        (b"rTRC", courbe), (b"gTRC", courbe), (b"bTRC", courbe),
        (b"cprt", b"text\0\0\0\0domaine public\0"),
    ]
    debut = 128 + 4 + 12 * len(balises)
    table, donnees = b"", b""
    for signature, contenu in balises:
        while len(donnees) % 4:
            donnees += b"\0"
        table += signature + struct.pack(">II", debut + len(donnees), len(contenu))
        donnees += contenu
    corps = struct.pack(">I", len(balises)) + table + donnees
    entete = (
        struct.pack(">I", 128 + len(corps)) + b"\0\0\0\0" + bytes([2, 0x10, 0, 0])
        + b"mntrRGB XYZ " + b"\0" * 12 + b"acsp" + b"\0" * 24
        + struct.pack(">I", 0) + _s15f16(0.9642, 1.0, 0.8249) + b"\0" * 48
    )
    return entete + corps


def photo_bicolore(
    format="JPEG",
    *,
    taille=(64, 32),
    orientation=None,
    gps=True,
    xmp=False,
    icc=None,
    couleurs=(ROUGE, BLEU),
) -> bytes:
    """Moitié gauche dans la 1re couleur, moitié droite dans la 2de : l'orientation se lit."""
    largeur, hauteur = taille
    img = Image.new("RGB", taille, couleurs[1])
    img.paste(couleurs[0], (0, 0, largeur // 2, hauteur))

    exif = Image.Exif()
    exif[0x010F], exif[0x0110] = "Apple", "iPhone 14 Pro Max"
    if orientation:
        exif[0x0112] = orientation
    exif.get_ifd(ExifTags.IFD.Exif)[0x9003] = "2025:04:05 14:30:00"
    if gps:
        ifd_gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
        ifd_gps[1], ifd_gps[2] = "N", _dms(35.6586)
        ifd_gps[3], ifd_gps[4] = "E", _dms(139.7454)

    options = {"exif": exif.tobytes()}
    if xmp:
        options["xmp"] = XMP
    if icc:
        options["icc_profile"] = icc
    tampon = io.BytesIO()
    img.save(tampon, format=format, quality=95, **options)
    return tampon.getvalue()


class CacheTemporaire:
    """Mixin de test : MEDIA_ROOT pointe vers un dossier temporaire (jamais le vrai cache)."""

    def setUp(self):
        super().setUp()
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        reglage = override_settings(MEDIA_ROOT=dossier.name)
        reglage.enable()
        self.addCleanup(reglage.disable)
        from pathlib import Path

        self.cache = Path(dossier.name)


# --- Vidéos et photos animées --------------------------------------------------

import shutil
import subprocess
from pathlib import Path

FFMPEG = shutil.which("ffmpeg")


def video(
    *,
    duree=1.0,
    taille=(320, 240),
    ips=30,
    son=True,
    rotation=None,
    location="+35.6586+139.7454/",
    creation_time="2025-04-05T05:30:00.000000Z",
    format="mp4",
    moov_a_la_fin=True,
    hdr=False,
) -> bytes:
    """Petite vidéo synthétique (mire ffmpeg), avec position GPS et date.

    Écrite dans un dossier temporaire le temps de la produire (rien à voir avec
    un original Nextcloud), puis renvoyée en octets.
    """
    largeur, hauteur = taille
    with tempfile.TemporaryDirectory() as dossier:
        sortie = Path(dossier) / f"v.{format}"
        cmd = ["ffmpeg", "-v", "error", "-y",
               "-f", "lavfi", "-i", f"testsrc2=size={largeur}x{hauteur}:rate={ips}:duration={duree}"]
        if son:
            cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={duree}"]
        cmd += ["-map", "0:v"] + (["-map", "1:a", "-c:a", "aac"] if son else [])
        if hdr:
            # HDR10 comme un Samsung : HEVC 10 bits, transfert PQ, couleurs BT.2020.
            cmd += ["-c:v", "libx265", "-pix_fmt", "yuv420p10le",
                    "-x265-params", "log-level=error:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc"
                    ":hdr10=1:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1)"
                    ":max-cll=1000,200"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
        if location:
            cmd += ["-metadata", f"location={location}", "-metadata", f"location-eng={location}"]
        if creation_time:
            cmd += ["-metadata", f"creation_time={creation_time}"]
        if not moov_a_la_fin:
            cmd += ["-movflags", "+faststart"]
        subprocess.run([*cmd, str(sortie)], check=True, capture_output=True)
        if rotation is not None:
            # Rotation « d'affichage » (comme un téléphone tenu verticalement), sans réencoder.
            tournee = Path(dossier) / f"r.{format}"
            subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-display_rotation", str(rotation), "-i", str(sortie),
                 "-c", "copy", "-map_metadata", "0", str(tournee)],
                check=True, capture_output=True,
            )
            sortie = tournee
        return sortie.read_bytes()


def boite(nom: bytes, contenu: bytes, taille_64_bits=False) -> bytes:
    if taille_64_bits:
        return struct.pack(">I4sQ", 1, nom, 16 + len(contenu)) + contenu
    return struct.pack(">I4s", 8 + len(contenu), nom) + contenu


def photo_animee(video_embarquee: bytes | None = None, **kwargs_image) -> bytes:
    """HEIC suivi d'une boîte `mpvd` contenant une vidéo, comme un Samsung S24
    (puis une boîte `sefd`, que Samsung place après)."""
    if video_embarquee is None:
        video_embarquee = video(duree=0.5, taille=(160, 120), location=None)
    kwargs_image.setdefault("lat", 35.0)
    kwargs_image.setdefault("lon", 139.0)
    heic = image("HEIF", **kwargs_image)
    return heic + boite(b"mpvd", video_embarquee) + boite(b"sefd", b"\0" * 32)
