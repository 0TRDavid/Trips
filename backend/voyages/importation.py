"""Import d'un dossier Nextcloud en Voyage, Jours et Photos.

Relançable : une photo dont l'etag n'a pas changé n'est ni retéléchargée ni
modifiée. Une photo déplacée dans Nextcloud (même etag, même nom, autre dossier)
garde son identité. Le premier sous-dossier sous le dossier du voyage désigne le
photographe (« Japon/Hugo/IMG_1.CR2 » → « Hugo »). Ce que l'auteur a saisi (titres, récits, légendes, favoris,
visibilité, ordre) n'est jamais écrasé.
"""

from __future__ import annotations

import posixpath
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timezone as dt_timezone
from datetime import tzinfo
from typing import Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.db.models import F, Max, Min
from django.utils import timezone
from django.utils.text import slugify

from .exif import analyser_decalage, extraire_metadonnees
from .models import Jour, Photo, Voyage
from .nextcloud import FichierDistant, normaliser


class ImportErreur(Exception):
    pass


class Client(Protocol):
    def lister(self, dossier: str) -> list[FichierDistant]: ...
    def telecharger(self, chemin: str, limite: int | None = None) -> bytes: ...


# Formats dont les EXIF sont en tête de fichier : inutile de télécharger les
# 20 à 30 Mo d'un RAW pour lire sa date.
OCTETS_EN_TETE = {".cr2": 256 * 1024}


@dataclass
class Rapport:
    voyage: Voyage | None = None
    dossier: str = ""
    images_nextcloud: int = 0
    photos_en_base: int = 0
    creees: int = 0
    mises_a_jour: int = 0
    inchangees: int = 0
    deplacees: int = 0
    sans_date: list[str] = field(default_factory=list)
    ignores: Counter = field(default_factory=Counter)
    disparues: list[str] = field(default_factory=list)
    dry_run: bool = False
    limite: int | None = None
    # Dossier du voyage avant son renommage dans Nextcloud (--ancien-dossier).
    renomme_depuis: str | None = None


def charger_fuseau(nom: str) -> ZoneInfo:
    try:
        return ZoneInfo(nom)
    except (ZoneInfoNotFoundError, ValueError):
        raise ImportErreur(f"Fuseau horaire inconnu : « {nom} » (exemple : Asia/Tokyo)") from None


def charger_horloge(valeur: str) -> tzinfo:
    """« UTC », « Europe/Paris » ou un décalage fixe « +01:00 »."""
    return analyser_decalage(valeur) or charger_fuseau(valeur)


def importer_voyage(
    client: Client,
    dossier: str,
    *,
    fuseau: str | None = None,
    auteur=None,
    titre: str | None = None,
    horloges: dict[str, str] | None = None,
    limite: int | None = None,
    dry_run: bool = False,
    ancien_dossier: str | None = None,
    progression: Callable[[int, int, str], None] | None = None,
) -> Rapport:
    dossier = normaliser(dossier)
    rapport = Rapport(dossier=dossier, dry_run=dry_run, limite=limite)

    fichiers = client.lister(dossier)
    images = [f for f in fichiers if f.est_image]

    voyage = Voyage.objects.filter(dossier_nextcloud=dossier).first()
    if voyage is None and ancien_dossier:
        ancien = normaliser(ancien_dossier)
        voyage = Voyage.objects.filter(dossier_nextcloud=ancien).first()
        if voyage is None:
            raise ImportErreur(f"Aucun voyage importé depuis l'ancien dossier « {ancien} »")
        rapport.renomme_depuis = ancien
    elif voyage is None:
        _refuser_si_deja_importe(images)
    if voyage is None:
        if not fuseau:
            raise ImportErreur("Premier import de ce dossier : précise le fuseau avec --fuseau (ex. Asia/Tokyo)")
        if auteur is None and not dry_run:
            raise ImportErreur("Aucun auteur : crée un superuser ou précise --auteur")
        tz = charger_fuseau(fuseau)
    else:
        if fuseau and fuseau != voyage.fuseau_horaire:
            raise ImportErreur(
                f"Ce voyage est déjà en {voyage.fuseau_horaire} ; changer de fuseau "
                "n'est pas géré par l'import"
            )
        tz = charger_fuseau(voyage.fuseau_horaire)

    # Horloges par appareil : celles déjà mémorisées, complétées par l'option.
    anciennes_horloges = voyage.horloges_appareils if voyage else {}
    horloges = {**anciennes_horloges, **(horloges or {})}
    horloges_tz = {appareil: charger_horloge(valeur) for appareil, valeur in horloges.items()}
    # Les photos de ces appareils doivent être relues, même si leur etag n'a pas changé.
    appareils_a_relire = {a for a, v in horloges.items() if anciennes_horloges.get(a) != v}

    rapport.images_nextcloud = len(images)
    rapport.ignores = Counter(f.extension or "(sans extension)" for f in fichiers if not f.est_image)

    existantes = (
        {p.chemin_nextcloud: p for p in Photo.objects.filter(jour__voyage=voyage)}
        if voyage else {}
    )
    chemins_distants = {f.chemin for f in images}
    deplacements = _reperer_deplacements(existantes, images, chemins_distants)
    rapport.deplacees = len(deplacements)
    rapport.disparues = sorted(
        set(existantes) - chemins_distants - {p.chemin_nextcloud for p in deplacements.values()}
    )

    a_traiter = images[:limite] if limite else images

    def a_jour(photo, fichier):
        return photo.etag == fichier.etag and photo.appareil not in appareils_a_relire

    if dry_run:
        for fichier in a_traiter:
            photo = existantes.get(fichier.chemin) or deplacements.get(fichier.chemin)
            if photo is None:
                rapport.creees += 1
            elif not a_jour(photo, fichier):
                rapport.mises_a_jour += 1
            else:
                rapport.inchangees += 1
        rapport.voyage = voyage
        rapport.photos_en_base = len(existantes)
        return rapport

    if voyage is None:
        titre = titre or posixpath.basename(dossier)
        voyage = Voyage.objects.create(
            auteur=auteur,
            titre=titre,
            slug=_slug_unique(titre),
            dossier_nextcloud=dossier,
            fuseau_horaire=fuseau,
            horloges_appareils=horloges,
        )
    rapport.voyage = voyage

    if rapport.renomme_depuis:
        voyage.dossier_nextcloud = dossier
        voyage.save(update_fields=["dossier_nextcloud"])

    # Déplacements appliqués d'abord, sans rien télécharger : la photo garde son
    # id, ses rendus et tout ce que l'auteur a saisi.
    for chemin, photo in deplacements.items():
        del existantes[photo.chemin_nextcloud]
        photo.chemin_nextcloud = chemin
        photo.photographe = photographe_depuis_chemin(dossier, chemin)
        photo.save(update_fields=["chemin_nextcloud", "photographe"])
        existantes[chemin] = photo

    for i, fichier in enumerate(a_traiter, start=1):
        if progression:
            progression(i, len(a_traiter), fichier.chemin)
        photo = existantes.get(fichier.chemin)
        if photo is not None and a_jour(photo, fichier):
            rapport.inchangees += 1
            photographe = photographe_depuis_chemin(dossier, fichier.chemin)
            if photo.photographe != photographe:
                photo.photographe = photographe
                photo.save(update_fields=["photographe"])
            continue
        _importer_photo(client, voyage, tz, horloges_tz, fichier, photo, rapport, dossier)

    # Mémorisées seulement une fois les photos relues : si l'import est
    # interrompu avant, la relance détectera encore le changement.
    if horloges != voyage.horloges_appareils:
        voyage.horloges_appareils = horloges
        voyage.save(update_fields=["horloges_appareils"])
    _mettre_a_jour_dates(voyage)
    rapport.photos_en_base = Photo.objects.filter(jour__voyage=voyage).count()
    return rapport


def _refuser_si_deja_importe(images):
    """Un dossier inconnu dont les photos sont déjà en base est sans doute un
    voyage renommé dans Nextcloud : on refuse plutôt que de créer un doublon."""
    etags = {f.etag for f in images}
    voyage = (
        Voyage.objects.filter(jours__photos__etag__in=etags).distinct().first()
        if etags else None
    )
    if voyage is not None:
        raise ImportErreur(
            f"Des photos de ce dossier appartiennent déjà au voyage « {voyage.titre} » "
            f"(dossier « {voyage.dossier_nextcloud} »). Si le dossier a été renommé ou "
            f"déplacé dans Nextcloud, relance avec --ancien-dossier \"{voyage.dossier_nextcloud}\""
        )


def photographe_depuis_chemin(dossier: str, chemin: str) -> str:
    """Premier sous-dossier sous le dossier du voyage, vide à la racine."""
    dossier = normaliser(dossier)
    relatif = chemin[len(dossier) + 1:] if chemin.startswith(dossier + "/") else chemin
    parties = relatif.split("/")
    return parties[0] if len(parties) > 1 else ""


def _reperer_deplacements(existantes: dict[str, Photo], images, chemins_distants) -> dict[str, Photo]:
    """{nouveau chemin: photo} pour les photos disparues de leur ancien chemin et
    réapparues ailleurs avec le même etag et le même nom de fichier."""
    disparues = {
        (p.etag, posixpath.basename(chemin)): p
        for chemin, p in existantes.items()
        if chemin not in chemins_distants
    }
    deplacements = {}
    for fichier in images:
        if fichier.chemin in existantes:
            continue
        photo = disparues.pop((fichier.etag, posixpath.basename(fichier.chemin)), None)
        if photo is not None:
            deplacements[fichier.chemin] = photo
    return deplacements


def _lire_metadonnees(client, fichier: FichierDistant, tz, horloges_tz):
    """Télécharge en mémoire (l'en-tête seulement si possible) et lit les EXIF."""
    limite = OCTETS_EN_TETE.get(fichier.extension)
    if limite:
        meta = extraire_metadonnees(client.telecharger(fichier.chemin, limite=limite), tz, horloges_tz)
        if meta.prise_le is not None:
            return meta
        # En-tête insuffisant : on se rabat sur le fichier complet.
    return extraire_metadonnees(client.telecharger(fichier.chemin), tz, horloges_tz)


def _importer_photo(client, voyage, tz, horloges_tz, fichier: FichierDistant, photo: Photo | None, rapport, dossier):
    # Le fichier n'existe qu'en mémoire, le temps de lire ses EXIF.
    meta = _lire_metadonnees(client, fichier, tz, horloges_tz)

    sans_date = meta.prise_le is None
    if sans_date:
        rapport.sans_date.append(fichier.chemin)
        prise_le = (fichier.modifie_le or timezone.now()).astimezone(dt_timezone.utc)
    else:
        prise_le = meta.prise_le
    date_locale = prise_le.astimezone(tz).date()

    with transaction.atomic():
        jour, _ = Jour.objects.get_or_create(voyage=voyage, date=date_locale)
        champs = dict(
            jour=jour,
            etag=fichier.etag,
            prise_le=prise_le,
            latitude=meta.latitude,
            longitude=meta.longitude,
            altitude=meta.altitude,
            appareil=meta.appareil,
            photographe=photographe_depuis_chemin(dossier, fichier.chemin),
            orientation=meta.orientation,
        )
        if photo is None:
            # Sans date fiable, la photo est masquée en attendant une décision dans l'admin.
            Photo.objects.create(
                chemin_nextcloud=fichier.chemin, visible=not sans_date,
                ordre=_rang_chronologique(jour, prise_le), **champs
            )
            rapport.creees += 1
        else:
            if photo.jour_id != jour.id:
                # Elle change de jour (horloge corrigée) : elle s'intercale à son heure.
                champs["ordre"] = _rang_chronologique(jour, prise_le)
            for nom, valeur in champs.items():
                setattr(photo, nom, valeur)
            photo.save(update_fields=list(champs))
            rapport.mises_a_jour += 1


def _rang_chronologique(jour: Jour, prise_le) -> int:
    """Rang d'une photo ajoutée à un jour : juste après la dernière photo (dans
    l'ordre actuel) prise avant elle. Les suivantes reculent d'un cran : l'ordre
    choisi dans l'admin entre les photos existantes est préservé."""
    precedente = jour.photos.filter(prise_le__lte=prise_le).aggregate(m=Max("ordre"))["m"]
    rang = (precedente or 0) + 1
    jour.photos.filter(ordre__gte=rang).update(ordre=F("ordre") + 1)
    return rang


def _mettre_a_jour_dates(voyage: Voyage):
    bornes = Jour.objects.filter(voyage=voyage, photos__isnull=False).aggregate(
        debut=Min("date"), fin=Max("date")
    )
    voyage.date_debut, voyage.date_fin = bornes["debut"], bornes["fin"]
    voyage.save(update_fields=["date_debut", "date_fin"])


def _slug_unique(titre: str) -> str:
    base = slugify(titre)[:180] or "voyage"
    slug, n = base, 2
    while Voyage.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug
