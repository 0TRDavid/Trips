"""Compléter à la main la date et la position des médias qui n'en ont pas.

Surtout les médias WhatsApp (sans EXIF) et les photos d'appareils sans GPS.
Toutes les opérations s'appliquent à un média ou à un lot, et marquent la
valeur comme saisie à la main (source « manuel ») : un nouvel import ne
l'écrasera jamais. Les originaux Nextcloud ne sont pas touchés.

Quand la date change, le média passe dans le jour local correspondant (créé
si besoin, jamais supprimé : un jour vidé disparaît déjà du site), s'y insère
selon la règle chronologique de l'import, et devient visible. Le tracé GPS,
calculé à chaque appel d'API sur les médias visibles, suit tout seul.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Q

from .importation import _inserer_au_rang, _rang_chronologique, mettre_a_jour_dates
from .models import Jour, Photo, Source, Voyage

# Dans un lot daté d'un coup, chaque média suivant prend une seconde de plus :
# le lot garde son ordre.
ECART_LOT = timedelta(seconds=1)

# Un média « à compléter » : sans date fiable ou sans position.
A_COMPLETER = Q(source_date=Source.AUCUNE) | Q(date_a_confirmer=True) | Q(latitude__isnull=True)


class CompletionErreur(ValueError):
    pass


def ordre_du_lot(photos: Iterable[Photo]) -> list[Photo]:
    """Ordre dans lequel un lot est daté : date actuelle, puis nom (le numéro
    WhatsApp WAnnnn suit l'ordre d'arrivée)."""
    return sorted(photos, key=lambda p: (p.prise_le, str(p)))


def _voyage_unique(photos: list[Photo]) -> Voyage:
    if not photos:
        raise CompletionErreur("Aucun média sélectionné.")
    voyages = {p.jour.voyage_id for p in photos}
    if len(voyages) > 1:
        raise CompletionErreur("Les médias d'un lot doivent appartenir au même voyage.")
    return photos[0].jour.voyage


def _dater(photo: Photo, instant: datetime, voyage: Voyage, apres: Photo | None = None) -> None:
    """Pose la date d'un média, le range dans son jour et le rend visible.

    `apres` : média derrière lequel l'insérer s'il est dans le même jour (choix
    explicite « placer entre ») ; sinon, règle chronologique de l'import.
    """
    date_locale = instant.astimezone(ZoneInfo(voyage.fuseau_horaire)).date()
    jour, _ = Jour.objects.get_or_create(voyage=voyage, date=date_locale)
    autres = jour.photos.exclude(pk=photo.pk)
    if apres is not None and apres.jour_id == jour.id:
        apres.refresh_from_db(fields=["ordre"])
        rang = _inserer_au_rang(autres, apres.ordre + 1)
    else:
        rang = _rang_chronologique(jour, instant, exclure=photo)
    photo.jour = jour
    photo.ordre = rang
    photo.prise_le = instant
    photo.source_date = Source.MANUEL
    photo.date_a_confirmer = False
    photo.visible = True
    photo.save(update_fields=["jour", "ordre", "prise_le", "source_date", "date_a_confirmer", "visible"])


@transaction.atomic
def changer_date(photos: Iterable[Photo], instant: datetime, apres: Photo | None = None) -> None:
    """Date saisie : le premier média du lot la reçoit, les suivants +1 s chacun."""
    if instant.tzinfo is None:
        raise CompletionErreur("La date doit porter son fuseau.")
    photos = ordre_du_lot(photos)
    voyage = _voyage_unique(photos)
    precedent = apres
    for i, photo in enumerate(photos):
        _dater(photo, instant + i * ECART_LOT, voyage, apres=precedent)
        if precedent is not None:
            precedent = photo  # le suivant du lot se range derrière celui-ci
    mettre_a_jour_dates(voyage)


@transaction.atomic
def placer_entre(photos: Iterable[Photo], a: Photo, b: Photo) -> None:
    """Répartit le lot à intervalles égaux entre les médias A et B, juste après A."""
    photos = ordre_du_lot(photos)
    voyage = _voyage_unique(photos)
    ids = {p.pk for p in photos}
    if a.pk in ids or b.pk in ids:
        raise CompletionErreur("Les médias de référence ne peuvent pas faire partie de la sélection.")
    if a.jour.voyage_id != voyage.pk or b.jour.voyage_id != voyage.pk:
        raise CompletionErreur("Les médias de référence doivent être du même voyage.")
    if b.prise_le < a.prise_le:
        a, b = b, a
    pas = (b.prise_le - a.prise_le) / (len(photos) + 1)
    precedent = a
    for i, photo in enumerate(photos, start=1):
        _dater(photo, a.prise_le + i * pas, voyage, apres=precedent)
        precedent = photo
    mettre_a_jour_dates(voyage)


@transaction.atomic
def changer_position(photos: Iterable[Photo], latitude: float, longitude: float, altitude: float | None = None):
    photos = list(photos)
    _voyage_unique(photos)
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise CompletionErreur("Coordonnées hors limites.")
    for photo in photos:
        photo.latitude, photo.longitude, photo.altitude = latitude, longitude, altitude
        photo.source_position = Source.MANUEL
        photo.save(update_fields=["latitude", "longitude", "altitude", "source_position"])


@transaction.atomic
def reprendre_de(photos: Iterable[Photo], reference: Photo, *, position: bool = True, heure: bool = False) -> None:
    """Copie la position et/ou l'heure d'un média de référence (une voisine).

    Avec l'heure, le lot se range juste derrière la référence (+1 s chacun).
    """
    photos = list(photos)
    voyage = _voyage_unique(photos)
    if reference.pk in {p.pk for p in photos}:
        raise CompletionErreur("Le média de référence ne peut pas faire partie de la sélection.")
    if reference.jour.voyage_id != voyage.pk:
        raise CompletionErreur("Le média de référence doit être du même voyage.")
    if not (position or heure):
        raise CompletionErreur("Rien à reprendre : choisir la position, l'heure, ou les deux.")
    if position:
        if reference.latitude is None or reference.longitude is None:
            raise CompletionErreur("Le média de référence n'a pas de position.")
        changer_position(photos, reference.latitude, reference.longitude, reference.altitude)
    if heure:
        changer_date(photos, reference.prise_le + ECART_LOT, apres=reference)


@transaction.atomic
def confirmer_date(photos: Iterable[Photo]) -> None:
    """Garde la date actuelle (proposée par le nom, ou celle du fichier) et la
    marque comme décidée par l'auteur : le média devient visible."""
    photos = list(photos)
    voyage = _voyage_unique(photos)
    for photo in photos:
        photo.source_date = Source.MANUEL
        photo.date_a_confirmer = False
        photo.visible = True
        photo.save(update_fields=["source_date", "date_a_confirmer", "visible"])
    mettre_a_jour_dates(voyage)
