"""Écrit dans Nextcloud les sidecars XMP des médias complétés à la main.

Idempotent : un sidecar dont l'empreinte (chemin + contenu) n'a pas changé
n'est pas réécrit ; un échec est signalé et retenté à la prochaine relance.
N'écrit que sous NEXTCLOUD_DOSSIER_EXPORT (vérifié par le client WebDAV), et
refuse un dossier d'export qui recouvre un dossier de voyage.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field

from django.db.models import Q

from .models import Photo, Source, Voyage
from .nextcloud import NextcloudErreur, normaliser
from .xmp import chemin_xmp, contenu_xmp, empreinte

TYPE_XMP = "application/rdf+xml"


class ExportErreur(Exception):
    pass


@dataclass
class RapportExport:
    ecrits: list[str] = field(default_factory=list)
    a_jour: int = 0
    erreurs: list[tuple[str, str]] = field(default_factory=list)
    dry_run: bool = False


def photos_avec_saisie(queryset=None):
    queryset = Photo.objects.all() if queryset is None else queryset
    return (
        queryset.filter(Q(source_date=Source.MANUEL) | Q(source_position=Source.MANUEL))
        .select_related("jour__voyage")
        .order_by("jour__voyage", "chemin_nextcloud")
    )


def verifier_dossier_export(dossier_export: str):
    """Le dossier d'export ne doit ni contenir un voyage, ni être dans un voyage."""
    export = normaliser(dossier_export)
    if not export:
        raise ExportErreur("NEXTCLOUD_DOSSIER_EXPORT n'est pas défini dans .env")
    for dossier in Voyage.objects.values_list("dossier_nextcloud", flat=True):
        voyage = normaliser(dossier)
        if export == voyage or export.startswith(voyage + "/") or voyage.startswith(export + "/"):
            raise ExportErreur(f"Le dossier d'export « {export} » recouvre le dossier du voyage « {voyage} »")


def exporter(client, photos, dossier_export: str, *, dry_run: bool = False, progression=None) -> RapportExport:
    verifier_dossier_export(dossier_export)
    rapport = RapportExport(dry_run=dry_run)
    dossiers_crees: set[str] = set()
    photos = list(photos)
    for i, photo in enumerate(photos, start=1):
        voyage = photo.jour.voyage
        contenu = contenu_xmp(photo, voyage.fuseau_horaire)
        if contenu is None:
            continue
        chemin = chemin_xmp(photo, voyage.dossier_nextcloud, dossier_export)
        signature = empreinte(chemin, contenu)
        if signature == photo.xmp_empreinte:
            rapport.a_jour += 1
            continue
        if progression:
            progression(i, len(photos), chemin)
        if dry_run:
            rapport.ecrits.append(chemin)
            continue
        try:
            dossier = posixpath.dirname(chemin)
            if dossier not in dossiers_crees:
                client.creer_dossiers(dossier)
                dossiers_crees.add(dossier)
            client.ecrire(chemin, contenu, TYPE_XMP)
        except NextcloudErreur as exc:
            rapport.erreurs.append((chemin, str(exc)))
            continue
        Photo.objects.filter(pk=photo.pk).update(xmp_empreinte=signature)
        rapport.ecrits.append(chemin)
    return rapport
