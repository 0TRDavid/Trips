"""Vidéos et photos animées : détection, entrée de ffmpeg, métadonnées.

Rien n'est jamais écrit sur disque :
- une vidéo Nextcloud est lue par ffmpeg/ffprobe directement sur son URL
  WebDAV, en flux (requêtes Range pour atteindre la boîte `moov`, souvent en
  fin de fichier) ;
- la vidéo embarquée d'une photo animée, déjà en mémoire, est passée à ffmpeg
  par un `memfd` (fichier anonyme en RAM) : un MP4 dont `moov` est à la fin
  ne se lit pas depuis un tube.

Photo animée Samsung (S24, HEIC) : la vidéo est une boîte ISO-BMFF de premier
niveau `mpvd` (« motion photo video data ») : 8 octets d'en-tête puis un MP4
complet. exiftool la nomme `QuickTime:MotionPhotoVideo`.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import struct
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, tzinfo

from .exif import Metadonnees, analyser_decalage, nom_appareil

# Clé de `Voyage.horloges_appareils` : fuseau dans lequel lire une date écrite
# dans le nom d'une vidéo (« 25-06-03 08-20-53 3981.mov »).
HORLOGE_NOM_DE_FICHIER = "nom de fichier"

DELAI_SONDE = 120  # secondes


class VideoErreur(Exception):
    pass


# --- Photo animée -------------------------------------------------------------

def video_embarquee(octets: bytes) -> slice | None:
    """Position du MP4 embarqué dans une photo animée Samsung, ou None.

    Parcourt les boîtes de premier niveau (tailles 32 ou 64 bits) jusqu'à
    `mpvd`. Un fichier tronqué ou abîmé renvoie None, sans erreur.
    """
    position, fin = 0, len(octets)
    while position + 8 <= fin:
        taille, nom = struct.unpack_from(">I4s", octets, position)
        entete = 8
        if taille == 1:  # taille 64 bits juste après le nom
            if position + 16 > fin:
                return None
            (taille,) = struct.unpack_from(">Q", octets, position + 8)
            entete = 16
        elif taille == 0:  # la boîte va jusqu'à la fin du fichier
            taille = fin - position
        if taille < entete or position + taille > fin:
            return None
        if nom == b"mpvd":
            debut = position + entete
            return slice(debut, position + taille) if position + taille > debut else None
        position += taille
    return None


# --- Entrée de ffmpeg / ffprobe ------------------------------------------------

@dataclass(frozen=True)
class Entree:
    """Arguments d'entrée de ffmpeg (« … -i <source> ») et descripteurs à transmettre."""

    args: tuple[str, ...]
    pass_fds: tuple[int, ...] = ()


@contextmanager
def entree_memoire(octets: bytes) -> Iterator[Entree]:
    """Des octets en mémoire vus par ffmpeg comme un fichier seekable, sans disque."""
    fd = os.memfd_create("video", os.MFD_CLOEXEC)
    try:
        _ecrire_tout(fd, octets)
        os.lseek(fd, 0, os.SEEK_SET)
        # ffmpeg rouvre /dev/fd/N : sa position de lecture est indépendante.
        yield Entree(args=("-i", f"/dev/fd/{fd}"), pass_fds=(fd,))
    finally:
        os.close(fd)


def _ecrire_tout(fd: int, octets: bytes):
    # os.write peut écrire moins que demandé : on boucle.
    vue = memoryview(octets)
    while vue:
        vue = vue[os.write(fd, vue):]


def executer(commande: list[str], entree: Entree, delai: int, sortie_texte=False) -> bytes:
    """Lance ffmpeg/ffprobe ; lève VideoErreur avec la fin du message d'erreur."""
    try:
        resultat = subprocess.run(
            commande, capture_output=True, timeout=delai, pass_fds=entree.pass_fds, check=False,
        )
    except subprocess.TimeoutExpired:
        raise VideoErreur(f"{commande[0]} : délai de {delai} s dépassé") from None
    except FileNotFoundError:
        raise VideoErreur(f"{commande[0]} introuvable (ffmpeg doit être installé)") from None
    if resultat.returncode != 0:
        message = resultat.stderr.decode(errors="replace").strip().splitlines()
        # Jamais l'en-tête d'authentification : seule la dernière ligne d'erreur.
        raise VideoErreur(f"{commande[0]} : {message[-1] if message else 'échec'}")
    return resultat.stdout


def sonder(entree: Entree) -> dict:
    """Métadonnées brutes (format et flux) lues par ffprobe."""
    sortie = executer(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", *entree.args],
        entree, DELAI_SONDE,
    )
    try:
        return json.loads(sortie)
    except ValueError:
        raise VideoErreur("ffprobe : réponse illisible") from None


# --- Caractéristiques du flux vidéo ---------------------------------------------

@dataclass(frozen=True)
class InfosVideo:
    largeur: int  # telle qu'affichée (rotation appliquée)
    hauteur: int
    duree: float | None
    ips: float | None  # images par seconde (moyenne)
    hdr: bool  # transfert PQ (HDR10) ou HLG : à convertir en SDR
    a_son: bool


def infos_video(sonde: dict) -> InfosVideo:
    flux = sonde.get("streams") or []
    video = next((f for f in flux if f.get("codec_type") == "video" and not _est_image_jointe(f)), None)
    if video is None:
        raise VideoErreur("aucune piste vidéo")
    largeur, hauteur = int(video.get("width") or 0), int(video.get("height") or 0)
    if not (largeur and hauteur):
        raise VideoErreur("dimensions de la vidéo inconnues")
    if _rotation(video) % 180:
        largeur, hauteur = hauteur, largeur
    return InfosVideo(
        largeur=largeur,
        hauteur=hauteur,
        duree=_duree(sonde, video),
        ips=_fraction(video.get("avg_frame_rate")) or _fraction(video.get("r_frame_rate")),
        hdr=video.get("color_transfer") in ("smpte2084", "arib-std-b67"),
        a_son=any(f.get("codec_type") == "audio" for f in flux),
    )


def _est_image_jointe(flux: dict) -> bool:
    return bool((flux.get("disposition") or {}).get("attached_pic"))


def _rotation(flux: dict) -> int:
    for donnee in flux.get("side_data_list") or []:
        if "rotation" in donnee:
            try:
                return int(round(float(donnee["rotation"])))
            except (TypeError, ValueError):
                return 0
    try:
        return int((flux.get("tags") or {}).get("rotate", 0))
    except (TypeError, ValueError):
        return 0


def _fraction(valeur) -> float | None:
    try:
        numerateur, _, denominateur = str(valeur).partition("/")
        resultat = float(numerateur) / float(denominateur or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    # « 90000/1 » : base de temps renvoyée à la place d'une vraie cadence.
    return resultat if 0 < resultat <= 240 else None


def _duree(sonde: dict, video: dict) -> float | None:
    for valeur in ((sonde.get("format") or {}).get("duration"), video.get("duration")):
        try:
            duree = float(valeur)
        except (TypeError, ValueError):
            continue
        if duree > 0:
            return round(duree, 2)
    return None


# --- Métadonnées (date, GPS, appareil) -------------------------------------------

_ISO6709 = re.compile(r"^([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)?")
_NOM_DATE = re.compile(r"^(\d{2})-(\d{2})-(\d{2}) (\d{2})-(\d{2})-(\d{2})(?!\d)")


def metadonnees_video(
    sonde: dict, fuseau: tzinfo, horloges: dict[str, tzinfo] | None = None, nom: str = ""
) -> Metadonnees:
    """Date (UTC), position, appareil et durée d'une vidéo, depuis la sortie de ffprobe.

    Date, par ordre de préférence :
    1. le nom du fichier « AA-MM-JJ HH-MM-SS… », si le voyage a une horloge
       « nom de fichier » (certains exports réécrivent la date interne) ;
    2. `com.apple.quicktime.creationdate`, qui porte le décalage horaire ;
    3. `creation_time` (UTC, norme QuickTime).
    Une date nulle (« 0000-00-00 », WhatsApp) ou d'avant 1990 est ignorée.
    """
    horloges = horloges or {}
    tags = _tags(sonde)
    latitude, longitude, altitude = _iso6709(
        tags.get("com.apple.quicktime.location.iso6709") or tags.get("location")
    )
    # Même nom que dans les EXIF des photos (« Apple iPhone 14 Pro Max ») : une
    # horloge réglée pour un appareil vaut pour ses photos et ses vidéos.
    appareil = nom_appareil(tags.get("com.apple.quicktime.make"), tags.get("com.apple.quicktime.model"))
    try:
        duree = infos_video(sonde).duree
    except VideoErreur:
        duree = None

    prise_le = None
    if HORLOGE_NOM_DE_FICHIER in horloges:
        prise_le = date_du_nom(nom, horloges[HORLOGE_NOM_DE_FICHIER])
    if prise_le is None:
        prise_le = _date_apple(tags.get("com.apple.quicktime.creationdate")) or _date_utc(tags.get("creation_time"))
    return Metadonnees(
        prise_le=prise_le,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        appareil=appareil,
        duree=duree,
    )


def date_du_nom(nom: str, fuseau: tzinfo) -> datetime | None:
    """« 25-06-03 08-20-53 3981.mov » lu dans `fuseau` → datetime UTC."""
    correspondance = _NOM_DATE.match(posixpath.basename(nom))
    if not correspondance:
        return None
    aa, mm, jj, h, mi, s = (int(v) for v in correspondance.groups())
    try:
        locale = datetime(2000 + aa, mm, jj, h, mi, s)
    except ValueError:
        return None
    return locale.replace(tzinfo=fuseau).astimezone(timezone.utc)


def nom_porte_une_date(nom: str) -> bool:
    return _NOM_DATE.match(posixpath.basename(nom)) is not None


def _tags(sonde: dict) -> dict[str, str]:
    """Balises du conteneur, clés en minuscules (complétées par celles des flux)."""
    tags = {}
    for flux in sonde.get("streams") or []:
        for cle, valeur in (flux.get("tags") or {}).items():
            tags.setdefault(cle.lower(), str(valeur))
    for cle, valeur in ((sonde.get("format") or {}).get("tags") or {}).items():
        tags[cle.lower()] = str(valeur)
    return tags


def _iso6709(valeur) -> tuple[float | None, float | None, float | None]:
    """« +35.0094+135.6745+161.226/ » → (35.0094, 135.6745, 161.23)."""
    correspondance = _ISO6709.match(str(valeur or "").strip())
    if not correspondance:
        return None, None, None
    lat, lon, alt = correspondance.groups()
    latitude, longitude = float(lat), float(lon)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180) or (latitude == 0 and longitude == 0):
        return None, None, None
    return round(latitude, 7), round(longitude, 7), round(float(alt), 2) if alt else None


def _valide(date: datetime) -> datetime | None:
    return date if date.year >= 1990 else None


def _date_apple(valeur) -> datetime | None:
    """« 2025-06-05T10:03:47+0900 » (décalage obligatoire)."""
    texte = str(valeur or "").strip()
    try:
        locale = datetime.strptime(texte[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    decalage = analyser_decalage(texte[19:])
    if decalage is None:
        return None
    return _valide(locale.replace(tzinfo=decalage).astimezone(timezone.utc))


def _date_utc(valeur) -> datetime | None:
    """« 2025-06-01T13:16:32.000000Z » : UTC."""
    texte = str(valeur or "").strip()
    try:
        date = datetime.strptime(texte[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return None
    return _valide(date.replace(tzinfo=timezone.utc))
