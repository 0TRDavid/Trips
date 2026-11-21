"""Génération des rendus web des médias en base, en parallèle.

Deux pistes, régénérées indépendamment :
- images (WebP) : la photo, ou l'aperçu (poster) d'une vidéo ; le poster d'une
  photo animée est son image fixe ;
- vidéos (MP4) : la vidéo, ou la vidéo embarquée d'une photo animée.

Relançable : une piste dont les rendus correspondent à l'etag courant, et dont
les fichiers sont bien sur disque, n'est ni retéléchargée ni retraitée. Une
photo déjà rendue qui se révèle animée ne reçoit que ses vidéos.

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
from .rendus_video import TAILLES_VIDEO, ResultatVideo, produire_apercu, produire_videos
from .video import entree_memoire, infos_video, sonder, video_embarquee

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
    type: str = Photo.Type.PHOTO
    images: bool = True  # (re)générer les WebP
    videos: bool = False  # (re)générer les MP4


@dataclass
class _Resultat:
    images: ResultatRendu | None = None
    videos: ResultatVideo | None = None


def racine_cache() -> Path:
    return Path(settings.MEDIA_ROOT)


def a_des_videos(photo: Photo) -> bool:
    return photo.type in (Photo.Type.ANIMEE, Photo.Type.VIDEO)


def images_a_jour(photo: Photo, racine: Path) -> bool:
    """Vrai si les trois WebP correspondent à l'etag courant et existent sur disque."""
    if not photo.rendus_etag or photo.rendus_etag != photo.etag:
        return False
    rendus = [r for r in photo.rendus.all() if r.taille in TAILLES]
    if {r.taille for r in rendus} != set(TAILLES):
        return False
    return all((racine / r.fichier).is_file() for r in rendus)


def videos_a_jour(photo: Photo, racine: Path) -> bool:
    """Vrai si le média n'a pas de vidéo, ou si ses MP4 (une ou deux tailles
    selon la source) correspondent à l'etag courant et existent sur disque."""
    if not a_des_videos(photo):
        return True
    if not photo.videos_etag or photo.videos_etag != photo.etag:
        return False
    rendus = [r for r in photo.rendus.all() if r.taille in TAILLES_VIDEO]
    return bool(rendus) and all((racine / r.fichier).is_file() for r in rendus)


def rendus_a_jour(photo: Photo, racine: Path) -> bool:
    return images_a_jour(photo, racine) and videos_a_jour(photo, racine)


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
    taches = [
        _Tache(
            p.id, p.chemin_nextcloud, p.etag, racine, p.type,
            images=force or not images_a_jour(p, racine),
            videos=a_des_videos(p) and (force or not videos_a_jour(p, racine)),
        )
        for p in a_faire
    ]
    # Les vidéos d'abord : ce sont les plus longues, autant les lancer tôt
    # pour que les processus finissent ensemble.
    taches.sort(key=lambda t: (t.type != Photo.Type.VIDEO, not t.videos))
    processus = max(1, processus or PROCESSUS_PAR_DEFAUT)

    for i, (tache, resultat, erreur) in enumerate(_executer(taches, fabrique_client, processus), start=1):
        if progression:
            progression(i, len(taches), tache.chemin)
        if erreur:
            rapport.erreurs.append((tache.chemin, erreur))
            continue
        _enregistrer(photos[tache.photo_id], tache, resultat, racine)
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


def _traiter(tache: _Tache) -> tuple[_Tache, _Resultat | None, str | None]:
    """Lit l'original (en mémoire, ou en flux pour une vidéo) et écrit ses
    rendus. Jamais d'accès à la base."""
    prefixe = prefixe_fichiers(tache.photo_id, tache.etag)
    resultat = _Resultat()
    try:
        if tache.type == Photo.Type.VIDEO:
            with _client.entree_video(tache.chemin) as entree:
                infos = infos_video(sonder(entree))
                if tache.images:
                    resultat.images = produire_apercu(entree, tache.racine, prefixe, infos)
                if tache.videos:
                    resultat.videos = produire_videos(entree, tache.racine, prefixe, son=True, infos=infos)
        else:
            octets = _client.telecharger(tache.chemin)
            if tache.images:
                resultat.images = produire_rendus(octets, tache.racine, prefixe)
            if tache.videos:
                position = video_embarquee(octets)
                if position is None:
                    raise ValueError("vidéo embarquée introuvable")
                # Photo animée : sans le son, comme sur le téléphone.
                with entree_memoire(octets[position]) as entree:
                    resultat.videos = produire_videos(entree, tache.racine, prefixe, son=False)
    except Exception as exc:  # un média abîmé ne doit pas arrêter les autres
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

def _remplacer(photo: Photo, tailles, fichiers, format: str):
    photo.rendus.filter(taille__in=list(tailles)).delete()
    Rendu.objects.bulk_create(
        Rendu(
            photo=photo, taille=f.taille, format=format,
            largeur=f.largeur, hauteur=f.hauteur, octets=f.octets, fichier=f.fichier,
        )
        for f in fichiers
    )


def _enregistrer(photo: Photo, tache: _Tache, resultat: _Resultat, racine: Path):
    # L'etag lu au moment du téléchargement : si le fichier a changé entre-temps,
    # la prochaine relance le verra.
    champs = []
    with transaction.atomic():
        if resultat.images is not None:
            images = resultat.images
            _remplacer(photo, TAILLES, images.fichiers, "webp")
            photo.largeur, photo.hauteur = images.largeur, images.hauteur
            photo.couleur, photo.placeholder = images.couleur, images.placeholder
            photo.couleurs = images.couleurs
            photo.rendus_etag = tache.etag
            champs += ["largeur", "hauteur", "couleur", "placeholder", "couleurs", "rendus_etag"]
        if resultat.videos is not None:
            _remplacer(photo, TAILLES_VIDEO, resultat.videos.fichiers, "mp4")
            photo.videos_etag = tache.etag
            champs.append("videos_etag")
            if resultat.videos.infos.duree and photo.duree is None:
                photo.duree = resultat.videos.infos.duree
                champs.append("duree")
        photo.save(update_fields=champs)
        a_garder = set(photo.rendus.values_list("fichier", flat=True))
    _supprimer_anciens_fichiers(racine, photo.id, a_garder)


def _supprimer_anciens_fichiers(racine: Path, photo_id: int, a_garder: set[str]):
    dossier = racine / "rendus" / str(photo_id)
    for fichier in dossier.iterdir():
        if fichier.relative_to(racine).as_posix() not in a_garder:
            fichier.unlink(missing_ok=True)
