"""Recherche d'un lieu par son nom : Nominatim (OpenStreetMap), côté serveur.

Politique d'usage de Nominatim (https://operations.osmfoundation.org/policies/nominatim/),
respectée ici :
- au plus une requête par seconde (verrou dans le processus) ;
- un User-Agent qui identifie l'application ; contact facultatif via
  NOMINATIM_CONTACT dans .env (aucune donnée personnelle par défaut) ;
- pas d'autocomplétion : on ne cherche que sur demande explicite (Entrée) ;
- résultats mis en cache en base (LieuCherche) : une même recherche n'est
  jamais renvoyée au service ;
- attribution « © OpenStreetMap » affichée à côté des résultats.
"""

from __future__ import annotations

import threading
import time

import requests
from django.conf import settings

from .models import LieuCherche

URL = "https://nominatim.openstreetmap.org/search"
INTERVALLE_S = 1.0
DELAI_S = 10
NB_RESULTATS = 6
LONGUEUR_MAX = 300

_verrou = threading.Lock()
_derniere_requete = 0.0


class GeocodageErreur(Exception):
    pass


def user_agent() -> str:
    contact = getattr(settings, "NOMINATIM_CONTACT", "")
    return f"CarnetDeVoyages/1.0 ({contact or 'carnet privé auto-hébergé'})"


def normaliser(requete: str) -> str:
    return " ".join(requete.split()).strip()[:LONGUEUR_MAX]


def _cle(requete: str, autour: tuple[float, float, float, float] | None) -> str:
    cle = requete.casefold()
    if autour:
        cle += " @" + ",".join(f"{v:.1f}" for v in autour)
    return cle


def _attendre_son_tour():
    global _derniere_requete
    attente = _derniere_requete + INTERVALLE_S - time.monotonic()
    if attente > 0:
        time.sleep(attente)
    _derniere_requete = time.monotonic()


def chercher(requete: str, autour: tuple[float, float, float, float] | None = None) -> list[dict]:
    """[{"nom", "lat", "lon"}, …] pour une recherche libre.

    `autour` (ouest, sud, est, nord) : zone du voyage, qui favorise les
    résultats proches sans exclure les autres.
    """
    requete = normaliser(requete)
    if len(requete) < 2:
        return []
    autour = tuple(round(v, 1) for v in autour) if autour else None
    cle = _cle(requete, autour)
    en_cache = LieuCherche.objects.filter(requete=cle).first()
    if en_cache is not None:
        return en_cache.resultats

    params = {"q": requete, "format": "jsonv2", "limit": NB_RESULTATS, "accept-language": "fr"}
    if autour:
        params["viewbox"] = ",".join(str(v) for v in autour)
    with _verrou:
        _attendre_son_tour()
        try:
            reponse = requests.get(URL, params=params, headers={"User-Agent": user_agent()}, timeout=DELAI_S)
            reponse.raise_for_status()
            bruts = reponse.json()
        except (requests.RequestException, ValueError) as exc:
            raise GeocodageErreur(f"Recherche de lieu impossible ({exc.__class__.__name__})") from None

    resultats = [
        {"nom": r.get("display_name", ""), "lat": float(r["lat"]), "lon": float(r["lon"])}
        for r in bruts
        if "lat" in r and "lon" in r
    ]
    LieuCherche.objects.update_or_create(requete=cle, defaults={"resultats": resultats})
    return resultats
