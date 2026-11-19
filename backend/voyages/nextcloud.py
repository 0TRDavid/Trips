"""Client WebDAV minimal pour Nextcloud, en lecture seule.

Deux opérations seulement : lister un dossier (PROPFIND) et télécharger un
fichier en mémoire (GET). Rien n'est jamais écrit dans Nextcloud ni sur disque.
"""

from __future__ import annotations

import posixpath
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# .cr2 : RAW Canon (TIFF), dont Pillow lit les EXIF.
EXTENSIONS_IMAGES = {".heic", ".heif", ".jpg", ".jpeg", ".cr2"}

DAV = "{DAV:}"
CORPS_PROPFIND = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:resourcetype/>
    <d:getetag/>
    <d:getcontentlength/>
    <d:getlastmodified/>
  </d:prop>
</d:propfind>"""


class NextcloudErreur(Exception):
    """Erreur lisible renvoyée par le client (jamais de mot de passe dedans)."""


@dataclass(frozen=True)
class FichierDistant:
    # Chemin relatif à la racine de l'utilisateur, sans « / » initial.
    chemin: str
    etag: str
    taille: int | None
    modifie_le: datetime | None
    est_dossier: bool = False

    @property
    def extension(self) -> str:
        return posixpath.splitext(self.chemin)[1].lower()

    @property
    def est_image(self) -> bool:
        return not self.est_dossier and self.extension in EXTENSIONS_IMAGES


def normaliser(chemin: str) -> str:
    """« /Shared/Japon/ » → « Shared/Japon »."""
    return chemin.strip().strip("/")


def analyser_propfind(xml: bytes | str, prefixe_dav: str) -> list[FichierDistant]:
    """Transforme une réponse PROPFIND en liste de fichiers et de dossiers.

    `prefixe_dav` est le chemin d'URL de la racine de l'utilisateur
    (« /remote.php/dav/files/carnet/ »), retiré des href renvoyés.
    """
    racine = ET.fromstring(xml)
    elements = []
    for reponse in racine.iter(f"{DAV}response"):
        href = unquote(reponse.findtext(f"{DAV}href", default=""))
        if href.startswith(prefixe_dav):
            href = href[len(prefixe_dav):]
        chemin = normaliser(href)

        prop = _prop_ok(reponse)
        if prop is None:
            continue
        type_ressource = prop.find(f"{DAV}resourcetype")
        est_dossier = (
            type_ressource is not None
            and type_ressource.find(f"{DAV}collection") is not None
        )
        taille = prop.findtext(f"{DAV}getcontentlength")
        modifie = prop.findtext(f"{DAV}getlastmodified")
        elements.append(
            FichierDistant(
                chemin=chemin,
                etag=(prop.findtext(f"{DAV}getetag") or "").strip('"'),
                taille=int(taille) if taille else None,
                modifie_le=parsedate_to_datetime(modifie) if modifie else None,
                est_dossier=est_dossier,
            )
        )
    return elements


def _prop_ok(reponse: ET.Element) -> ET.Element | None:
    """Renvoie le bloc <prop> dont le statut est 200."""
    for propstat in reponse.findall(f"{DAV}propstat"):
        if " 200 " in (propstat.findtext(f"{DAV}status") or ""):
            return propstat.find(f"{DAV}prop")
    return None


class ClientWebDAV:
    def __init__(self, url: str, utilisateur: str, mot_de_passe: str, timeout: int = 60):
        if not (url and utilisateur and mot_de_passe):
            raise NextcloudErreur(
                "NEXTCLOUD_URL, NEXTCLOUD_USER et NEXTCLOUD_PASSWORD doivent être définis dans .env"
            )
        self.racine = f"{url.rstrip('/')}/remote.php/dav/files/{quote(utilisateur)}/"
        self.prefixe_dav = unquote(urlparse(self.racine).path)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (utilisateur, mot_de_passe)
        nouvelles_tentatives = Retry(
            total=3, backoff_factor=1, status_forcelist=[502, 503, 504],
            allowed_methods=None,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=nouvelles_tentatives))
        self.session.mount("http://", HTTPAdapter(max_retries=nouvelles_tentatives))

    def url(self, chemin: str) -> str:
        """URL encodée d'un chemin (espaces, accents, parenthèses…)."""
        return self.racine + quote(normaliser(chemin))

    def lister(self, dossier: str) -> list[FichierDistant]:
        """Liste récursivement les fichiers (pas les dossiers) sous `dossier`."""
        fichiers = []
        a_parcourir = [normaliser(dossier)]
        while a_parcourir:
            courant = a_parcourir.pop()
            for element in self._propfind(courant):
                if element.chemin == courant:
                    continue  # la réponse inclut le dossier lui-même
                if element.est_dossier:
                    a_parcourir.append(element.chemin)
                else:
                    fichiers.append(element)
        return sorted(fichiers, key=lambda f: f.chemin)

    def telecharger(self, chemin: str, limite: int | None = None) -> bytes:
        """Télécharge un fichier en mémoire. Rien n'est écrit sur disque.

        Avec `limite`, seuls les premiers octets sont demandés (en-tête EXIF).
        """
        headers = {"Range": f"bytes=0-{limite - 1}"} if limite else {}
        reponse = self._requete("GET", chemin, headers=headers)
        return reponse.content

    def _propfind(self, dossier: str) -> list[FichierDistant]:
        url = self.url(dossier)
        if not url.endswith("/"):
            url += "/"
        reponse = self._requete(
            "PROPFIND", dossier, url=url, data=CORPS_PROPFIND.encode(),
            headers={"Depth": "1", "Content-Type": "application/xml; charset=utf-8"},
        )
        return analyser_propfind(reponse.content, self.prefixe_dav)

    def _requete(self, methode: str, chemin: str, url: str | None = None, **kwargs):
        try:
            reponse = self.session.request(
                methode, url or self.url(chemin), timeout=self.timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise NextcloudErreur(f"Nextcloud injoignable ({type(exc).__name__})") from None
        if reponse.status_code == 401:
            raise NextcloudErreur("Nextcloud refuse l'authentification (401) : vérifie NEXTCLOUD_USER et NEXTCLOUD_PASSWORD")
        if reponse.status_code == 404:
            raise NextcloudErreur(f"Introuvable dans Nextcloud (404) : « {chemin} »")
        if reponse.status_code >= 400:
            raise NextcloudErreur(f"Nextcloud a répondu {reponse.status_code} pour « {chemin} »")
        return reponse
