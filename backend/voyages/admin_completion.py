"""Écran « Compléter les médias » de l'admin : page sur mesure et ses endpoints JSON.

Réservé à l'équipe (admin_view + permission de modifier les médias), CSRF sur
les écritures. Ces endpoints ne font pas partie de l'API publique (qui reste en
lecture seule et sans coordonnées par photo) : ils servent l'admin uniquement.
La logique d'écriture vit dans voyages/completion.py.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Max, Min, Q
from django.http import Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render
from django.urls import path, reverse

from . import completion, geocodage
from .models import Jour, Photo, Source, Voyage
from .trace import construire_trace

FILTRES = {
    "a_completer": completion.A_COMPLETER,
    "sans_date": Q(source_date=Source.AUCUNE),
    "a_confirmer": Q(date_a_confirmer=True),
    "sans_position": Q(latitude__isnull=True),
    "tout": Q(),
}
MARGE_ZONE_DEG = 0.5  # autour des positions du voyage, pour orienter la recherche de lieux


def urls(admin_site):
    vue = admin_site.admin_view
    return [
        path("completer/", vue(lambda request: page(request, admin_site)), name="voyages_photo_completer"),
        path("completer/medias/", vue(medias), name="voyages_completer_medias"),
        path("completer/voyage/", vue(contexte_voyage), name="voyages_completer_voyage"),
        path("completer/jour/", vue(medias_du_jour), name="voyages_completer_jour"),
        path("completer/appliquer/", vue(appliquer), name="voyages_completer_appliquer"),
        path("completer/lieux/", vue(lieux), name="voyages_completer_lieux"),
    ]


def _exiger_permission(request):
    if not request.user.has_perm("voyages.change_photo"):
        raise PermissionDenied


def _voyage(request) -> Voyage:
    try:
        return Voyage.objects.get(pk=int(request.GET.get("voyage", "")))
    except (ValueError, Voyage.DoesNotExist):
        raise Http404("Voyage inconnu") from None


def _url_rendu(photo: Photo, taille: str) -> str | None:
    for rendu in photo.rendus.all():
        if rendu.taille == taille:
            return settings.MEDIA_URL + rendu.fichier
    return None


def serialiser(photo: Photo, tz: ZoneInfo) -> dict:
    local = photo.prise_le.astimezone(tz)
    return {
        "id": photo.pk,
        "nom": str(photo),
        "type": photo.type,
        "photographe": photo.photographe,
        "miniature": _url_rendu(photo, "miniature"),
        "image": _url_rendu(photo, "moyenne") or _url_rendu(photo, "miniature"),
        "couleur": photo.couleur or "#888888",
        "ratio": (photo.largeur / photo.hauteur) if photo.largeur and photo.hauteur else 1.5,
        "jour": photo.jour.date.isoformat(),
        "instant": local.isoformat(timespec="seconds"),
        "source_date": photo.source_date,
        "date_a_confirmer": photo.date_a_confirmer,
        "lat": photo.latitude,
        "lon": photo.longitude,
        "source_position": photo.source_position,
        "visible": photo.visible,
        "ordre": photo.ordre,
    }


def _requete_medias(voyage: Voyage):
    return (
        Photo.objects.filter(jour__voyage=voyage)
        .select_related("jour__voyage")
        .prefetch_related("rendus")
    )


# --- Page ------------------------------------------------------------------------


def page(request, admin_site):
    _exiger_permission(request)
    voyages = list(Voyage.objects.annotate(
        nb_a_completer=Count("jours__photos", filter=_prefixer(completion.A_COMPLETER))
    ).order_by("-date_debut"))
    choisi = request.GET.get("voyage")
    config = {
        "voyages": [{"id": v.pk, "titre": v.titre, "a_completer": v.nb_a_completer} for v in voyages],
        "voyage": int(choisi) if choisi and choisi.isdigit() else (voyages[0].pk if voyages else None),
        "urls": {
            "medias": reverse("admin:voyages_completer_medias"),
            "voyage": reverse("admin:voyages_completer_voyage"),
            "jour": reverse("admin:voyages_completer_jour"),
            "appliquer": reverse("admin:voyages_completer_appliquer"),
            "lieux": reverse("admin:voyages_completer_lieux"),
            "media": reverse("admin:voyages_photo_change", args=[0]),
        },
    }
    contexte = {
        **admin_site.each_context(request),
        "title": "Compléter les médias",
        "config": config,
    }
    return render(request, "admin/voyages/photo/completer.html", contexte)


def _prefixer(q: Q) -> Q:
    """Q sur Photo → même condition vue depuis Voyage (jours__photos__…)."""
    copie = Q()
    copie.connector, copie.negated = q.connector, q.negated
    for enfant in q.children:
        if isinstance(enfant, Q):
            copie.children.append(_prefixer(enfant))
        else:
            cle, valeur = enfant
            copie.children.append((f"jours__photos__{cle}", valeur))
    return copie


# --- Lecture ---------------------------------------------------------------------


def medias(request):
    """Médias du voyage selon le filtre, avec les comptes de chaque filtre."""
    _exiger_permission(request)
    voyage = _voyage(request)
    filtre = request.GET.get("filtre", "a_completer")
    if filtre not in FILTRES:
        filtre = "a_completer"
    tz = ZoneInfo(voyage.fuseau_horaire)
    base = _requete_medias(voyage)
    comptes = base.aggregate(**{nom: Count("id", filter=q) for nom, q in FILTRES.items()})
    liste = base.filter(FILTRES[filtre]).order_by("jour__date", "ordre", "prise_le")
    return JsonResponse({
        "filtre": filtre,
        "comptes": comptes,
        "medias": [serialiser(p, tz) for p in liste],
    })


def contexte_voyage(request):
    """Fuseau, jours (avec leur nombre de médias), tracé et positions connues : le
    décor de la carte et du choix du jour."""
    _exiger_permission(request)
    voyage = _voyage(request)
    jours = (
        Jour.objects.filter(voyage=voyage)
        .annotate(nb=Count("photos"), nb_visibles=Count("photos", filter=Q(photos__visible=True)))
        .order_by("date")
    )
    places = (
        Photo.objects.filter(jour__voyage=voyage, visible=True, latitude__isnull=False, longitude__isnull=False)
        .order_by("prise_le")
        .values_list("id", "jour__date", "latitude", "longitude")
    )
    places = list(places)
    zone = None
    if places:
        lats = [p[2] for p in places]
        lons = [p[3] for p in places]
        zone = [min(lons), min(lats), max(lons), max(lats)]
    return JsonResponse({
        "id": voyage.pk,
        "titre": voyage.titre,
        "fuseau": voyage.fuseau_horaire,
        "debut": voyage.date_debut.isoformat() if voyage.date_debut else None,
        "fin": voyage.date_fin.isoformat() if voyage.date_fin else None,
        "jours": [{"date": j.date.isoformat(), "nb": j.nb, "nb_visibles": j.nb_visibles} for j in jours],
        "trace": construire_trace((d, lat, lon) for _, d, lat, lon in places),
        "positions": [{"id": i, "jour": d.isoformat(), "lat": lat, "lon": lon} for i, d, lat, lon in places],
        "zone": zone,
    })


def medias_du_jour(request):
    """Tous les médias d'un jour, dans l'ordre du site (masqués compris, signalés)."""
    _exiger_permission(request)
    voyage = _voyage(request)
    try:
        jour_date = date.fromisoformat(request.GET.get("date", ""))
    except ValueError:
        raise Http404("Date invalide") from None
    tz = ZoneInfo(voyage.fuseau_horaire)
    liste = _requete_medias(voyage).filter(jour__date=jour_date).order_by("ordre", "prise_le")
    return JsonResponse({"date": jour_date.isoformat(), "medias": [serialiser(p, tz) for p in liste]})


def lieux(request):
    _exiger_permission(request)
    voyage = _voyage(request)
    zone = Photo.objects.filter(jour__voyage=voyage, latitude__isnull=False).aggregate(
        ouest=Min("longitude"), sud=Min("latitude"), est=Max("longitude"), nord=Max("latitude")
    )
    autour = None
    if zone["ouest"] is not None:
        m = MARGE_ZONE_DEG
        autour = (zone["ouest"] - m, zone["sud"] - m, zone["est"] + m, zone["nord"] + m)
    try:
        resultats = geocodage.chercher(request.GET.get("q", ""), autour)
    except geocodage.GeocodageErreur as exc:
        return JsonResponse({"erreur": str(exc)}, status=502)
    return JsonResponse({"resultats": resultats})


# --- Écriture --------------------------------------------------------------------


def _instant(valeur, tz: ZoneInfo) -> datetime:
    """« 2025-06-04T14:20[:05] » lu dans le fuseau du voyage (ou avec son décalage)."""
    try:
        instant = datetime.fromisoformat(str(valeur))
    except ValueError:
        raise completion.CompletionErreur("Date ou heure invalide.") from None
    return instant.replace(tzinfo=tz) if instant.tzinfo is None else instant


def _photo(voyage: Voyage, ident) -> Photo:
    try:
        return Photo.objects.select_related("jour__voyage").get(pk=int(ident), jour__voyage=voyage)
    except (TypeError, ValueError, Photo.DoesNotExist):
        raise completion.CompletionErreur("Média de référence introuvable.") from None


def _nombre(valeur, nom: str) -> float:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        raise completion.CompletionErreur(f"{nom} invalide.") from None


def appliquer(request):
    """POST JSON {voyage, ids, action, …} → applique l'action au lot.

    Actions : date {instant}, entre {a, b}, position {lat, lon}, reprendre
    {reference, position, heure}, confirmer.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    _exiger_permission(request)
    try:
        donnees = json.loads(request.body or b"{}")
        voyage = Voyage.objects.get(pk=int(donnees.get("voyage")))
    except (ValueError, TypeError, Voyage.DoesNotExist):
        return JsonResponse({"erreur": "Requête invalide."}, status=400)
    tz = ZoneInfo(voyage.fuseau_horaire)
    ids = [int(i) for i in donnees.get("ids", []) if str(i).isdigit()]
    photos = list(Photo.objects.select_related("jour__voyage").filter(pk__in=ids, jour__voyage=voyage))
    action = donnees.get("action")
    try:
        if len(photos) != len(set(ids)) or not photos:
            raise completion.CompletionErreur("Sélection vide ou hors de ce voyage.")
        if action == "date":
            completion.changer_date(photos, _instant(donnees.get("instant"), tz))
        elif action == "entre":
            completion.placer_entre(photos, _photo(voyage, donnees.get("a")), _photo(voyage, donnees.get("b")))
        elif action == "position":
            completion.changer_position(
                photos, _nombre(donnees.get("lat"), "Latitude"), _nombre(donnees.get("lon"), "Longitude")
            )
        elif action == "reprendre":
            completion.reprendre_de(
                photos, _photo(voyage, donnees.get("reference")),
                position=bool(donnees.get("position")), heure=bool(donnees.get("heure")),
            )
        elif action == "confirmer":
            completion.confirmer_date(photos)
        else:
            raise completion.CompletionErreur("Action inconnue.")
    except completion.CompletionErreur as exc:
        return JsonResponse({"erreur": str(exc)}, status=400)
    a_jour = _requete_medias(voyage).filter(pk__in=ids)
    return JsonResponse({"medias": [serialiser(p, tz) for p in a_jour]})
