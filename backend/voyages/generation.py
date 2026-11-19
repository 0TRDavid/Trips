"""Génération des rendus web pour les photos en base, en parallèle.

Relançable : une photo dont les rendus correspondent à l'etag courant, et dont
les fichiers sont bien sur disque, n'est ni retéléchargée ni retraitée.

Parallélisme : chaque processus fils télécharge un original en mémoire et
écrit ses rendus dans le cache, sans jamais toucher à la base. Seul le
processus principal écrit en base, une transaction par photo : un traitement
interrompu reprend là où il s'est arrêté.
"""

from __future__ import annotations

import multiprocessing
import os
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import connection, connections, transaction

from .models import Photo, Rendu, Voyage
from .rendus import TAILLES, ResultatRendu, prefixe_fichiers, produire_rendus

PROCESSUS_PAR_DEFAUT = min(4, os.cpu_count() or 1)


@dataclass
class RapportRendus:
    photos: int = 0
    generees: int = 0
    inchangees: int = 0
    erreurs: list[tuple[str, str]] = field(default_factory=list)
    duree: float = 0.0
    fichiers_cache: int = 0
    octets_cache: int = 0
    dry_run: bool = False


@dataclass(frozen=True)
class _Tache:
    photo_id: int
    chemin: str
    etag: str
    racine: Path


def racine_cache() -> Path:
    return Path(settings.MEDIA_ROOT)


def rendus_a_jour(photo: Photo, racine: Path) -> bool:
    """Vrai si les trois rendus correspondent à l'etag courant et existent sur disque."""
    if not photo.rendus_etag or photo.rendus_etag != photo.etag:
        return False
    rendus = list(photo.rendus.all())
    if {r.taille for r in rendus} != set(TAILLES):
        return False
    return all((racine / r.fichier).is_file() for r in rendus)


def photos_a_traiter(
    voyage: Voyage | None = None, force: bool = False, photos_ids: list[int] | None = None
) -> tuple[list[Photo], int]:
    """Renvoie (photos à (re)générer, nombre total de photos concernées)."""
    photos = Photo.objects.prefetch_related("rendus").order_by("id")
    if voyage is not None:
        photos = photos.filter(jour__voyage=voyage)
    if photos_ids is not None:
        photos = photos.filter(id__in=photos_ids)
    photos = list(photos)
    racine = racine_cache()
    a_faire = photos if force else [p for p in photos if not rendus_a_jour(p, racine)]
    return a_faire, len(photos)


def generer_rendus(
    *,
    fabrique_client: Callable[[], object],
    voyage: Voyage | None = None,
    photos_ids: list[int] | None = None,
    force: bool = False,
    processus: int | None = None,
    dry_run: bool = False,
    progression: Callable[[int, int, str], None] | None = None,
) -> RapportRendus:
    """Génère les rendus manquants ou périmés.

    `fabrique_client` crée un client Nextcloud ; elle est appelée une fois par
    processus (une connexion HTTP ne se partage pas entre processus).
    """
    debut = time.monotonic()
    a_faire, total = photos_a_traiter(voyage, force, photos_ids)
    rapport = RapportRendus(photos=total, inchangees=total - len(a_faire), dry_run=dry_run)
    if dry_run:
        rapport.generees = len(a_faire)
        return rapport

    racine = racine_cache()
    photos = {p.id: p for p in a_faire}
    taches = [_Tache(p.id, p.chemin_nextcloud, p.etag, racine) for p in a_faire]
    processus = max(1, processus or PROCESSUS_PAR_DEFAUT)

    for i, (tache, resultat, erreur) in enumerate(_executer(taches, fabrique_client, processus), start=1):
        if progression:
            progression(i, len(taches), tache.chemin)
        if erreur:
            rapport.erreurs.append((tache.chemin, erreur))
            continue
        _enregistrer(photos[tache.photo_id], tache.etag, resultat, racine)
        rapport.generees += 1

    rapport.duree = time.monotonic() - debut
    rapport.fichiers_cache, rapport.octets_cache = taille_cache(racine)
    return rapport


def taille_cache(racine: Path) -> tuple[int, int]:
    dossier = racine / "rendus"
    if not dossier.is_dir():
        return 0, 0
    fichiers = [f for f in dossier.rglob("*") if f.is_file()]
    return len(fichiers), sum(f.stat().st_size for f in fichiers)


# --- Exécution, dans ce processus ou dans des processus fils ----------------

_client = None  # un client par processus


def _initialiser(fabrique_client):
    global _client
    _client = fabrique_client()


def _traiter(tache: _Tache) -> tuple[_Tache, ResultatRendu | None, str | None]:
    """Télécharge l'original en mémoire et écrit ses rendus. Jamais d'accès à la base."""
    try:
        octets = _client.telecharger(tache.chemin)
        resultat = produire_rendus(octets, tache.racine, prefixe_fichiers(tache.photo_id, tache.etag))
    except Exception as exc:  # une photo abîmée ne doit pas arrêter les autres
        return tache, None, f"{type(exc).__name__} : {exc}"
    return tache, resultat, None


def _executer(taches, fabrique_client, processus):
    if not taches:
        return
    # Créé ici d'abord : une configuration manquante lève une erreur lisible
    # plutôt que de faire échouer les processus fils un par un.
    _initialiser(fabrique_client)
    if processus == 1 or len(taches) == 1:
        for tache in taches:
            yield _traiter(tache)
        return

    # fork : les fils héritent du code déjà chargé (Django, Pillow) sans le réimporter.
    # Ils n'utilisent pas la base ; on ferme quand même les connexions pour ne pas
    # partager de socket (sauf dans une transaction en cours, cas des tests).
    if not connection.in_atomic_block:
        connections.close_all()
    contexte = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=processus, mp_context=contexte,
        initializer=_initialiser, initargs=(fabrique_client,),
    ) as pool:
        futurs = [pool.submit(_traiter, tache) for tache in taches]
        for futur in as_completed(futurs):
            yield futur.result()


# --- Écriture en base (processus principal uniquement) ----------------------

def _enregistrer(photo: Photo, etag: str, resultat: ResultatRendu, racine: Path):
    with transaction.atomic():
        photo.rendus.all().delete()
        Rendu.objects.bulk_create(
            Rendu(
                photo=photo, taille=f.taille, format="webp",
                largeur=f.largeur, hauteur=f.hauteur, octets=f.octets, fichier=f.fichier,
            )
            for f in resultat.fichiers
        )
        photo.largeur, photo.hauteur = resultat.largeur, resultat.hauteur
        photo.couleur, photo.placeholder = resultat.couleur, resultat.placeholder
        # L'etag lu au moment du téléchargement : si le fichier a changé entre-temps,
        # la prochaine relance le verra.
        photo.rendus_etag = etag
        photo.save(update_fields=["largeur", "hauteur", "couleur", "placeholder", "rendus_etag"])
    _supprimer_anciens_fichiers(racine, photo.id, {f.fichier for f in resultat.fichiers})


def _supprimer_anciens_fichiers(racine: Path, photo_id: int, a_garder: set[str]):
    dossier = racine / "rendus" / str(photo_id)
    for fichier in dossier.iterdir():
        if fichier.relative_to(racine).as_posix() not in a_garder:
            fichier.unlink(missing_ok=True)
