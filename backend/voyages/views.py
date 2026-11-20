"""API en lecture seule pour le front.

Chaque vue charge tout ce dont elle a besoin en un nombre fixe de requêtes,
quel que soit le nombre de jours ou de photos (vérifié par les tests) :
comptes et photos « représentatives » calculés en SQL (annotations), puis
photos et rendus chargés en une fois.
"""

from datetime import date

from django.db.models import Count, Exists, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Jour, Photo, Voyage
from .serializers import (
    JourDetailSerializer,
    PhotoSerializer,
    VoyageDetailSerializer,
    VoyageResumeSerializer,
    fuseau,
)
from .trace import construire_trace

# --- Briques de requêtes ----------------------------------------------------

_ORDRE_REPRESENTATIVE = ("-favori", "ordre", "prise_le", "id")


def _compte(queryset, groupe: str):
    """Sous-requête de comptage (0 si rien). Évite la multiplication des lignes
    qu'entraînent plusieurs Count() sur des jointures différentes."""
    return Coalesce(
        Subquery(
            queryset.order_by().values(groupe).annotate(n=Count("id")).values("n"),
            output_field=IntegerField(),
        ),
        0,
    )


def _photo_representative_du_jour():
    """Premier favori visible du jour, sinon sa première photo visible."""
    return Subquery(
        Photo.objects.filter(jour=OuterRef("pk"), visible=True).order_by(*_ORDRE_REPRESENTATIVE).values("id")[:1]
    )


def _jours_affiches(jours):
    """Jours qui ont quelque chose à montrer : un média visible, ou un récit ou
    un titre écrits. Un jour qui ne contient que des médias masqués (photos
    WhatsApp sans date, rangées à la date du fichier) n'apparaît pas sur le site."""
    return jours.annotate(
        a_un_media_visible=Exists(Photo.objects.filter(jour=OuterRef("pk"), visible=True)),
    ).filter(Q(a_un_media_visible=True) | ~Q(recit="") | ~Q(titre=""))


def _voyages_annotes():
    return Voyage.objects.annotate(
        nb_jours=_compte(_jours_affiches(Jour.objects.filter(voyage=OuterRef("pk"))), "voyage"),
        nb_photos=_compte(Photo.objects.filter(jour__voyage=OuterRef("pk"), visible=True), "jour__voyage"),
        # Couverture choisie dans l'admin, sinon premier favori, sinon première photo.
        couverture_effective_id=Coalesce(
            "couverture_id",
            Subquery(
                Photo.objects.filter(jour__voyage=OuterRef("pk"), visible=True)
                .order_by("-favori", "jour__date", "ordre", "prise_le", "id")
                .values("id")[:1]
            ),
        ),
    )


def _jours_annotes(voyage):
    return _jours_affiches(Jour.objects.filter(voyage=voyage)).annotate(
        nb_photos=_compte(Photo.objects.filter(jour=OuterRef("pk"), visible=True), "jour"),
        photo_id=_photo_representative_du_jour(),
    )


def _charger_photos(ids) -> dict[int, Photo]:
    """{id: Photo} avec leurs rendus, en deux requêtes (aucune si la liste est vide)."""
    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {p.id: p for p in Photo.objects.filter(id__in=ids).prefetch_related("rendus")}


# --- Vues --------------------------------------------------------------------


class VoyagesView(APIView):
    """GET /api/voyages/ : les voyages, du plus récent au plus ancien."""

    def get(self, request):
        voyages = list(_voyages_annotes())
        photos = _charger_photos(v.couverture_effective_id for v in voyages)
        return Response(VoyageResumeSerializer(voyages, many=True, context={"photos": photos}).data)


class VoyageView(APIView):
    """GET /api/voyages/<slug>/ : détail, timeline des jours et tracé GPS."""

    def get(self, request, slug):
        voyage = get_object_or_404(_voyages_annotes(), slug=slug)
        jours = list(_jours_annotes(voyage).order_by("date"))
        photos = _charger_photos([voyage.couverture_effective_id, *(j.photo_id for j in jours)])
        positions = (
            Photo.objects.filter(
                jour__voyage=voyage, visible=True, latitude__isnull=False, longitude__isnull=False
            )
            .order_by("prise_le", "id")
            .values_list("jour__date", "latitude", "longitude")
        )
        contexte = {"photos": photos, "jours": jours, "trace": construire_trace(positions)}
        return Response(VoyageDetailSerializer(voyage, context=contexte).data)


class JourView(APIView):
    """GET /api/voyages/<slug>/jours/<date>/ : récit, photos visibles dans l'ordre,
    jours précédent et suivant."""

    def get(self, request, slug, date_iso):
        try:
            jour_date = date.fromisoformat(date_iso)
        except ValueError:
            raise Http404("Date invalide") from None
        jour = get_object_or_404(Jour.objects.select_related("voyage"), voyage__slug=slug, date=jour_date)

        # Tous les jours du voyage en une requête légère (date, titre, photo
        # représentative) : on y prend les voisins sans requête supplémentaire.
        jours = list(
            _jours_annotes(jour.voyage_id).order_by("date").only("id", "date", "titre", "voyage_id")
        )
        rang = next((i for i, j in enumerate(jours) if j.id == jour.id), None)
        if rang is None:
            raise Http404("Jour sans rien à montrer")
        precedent = jours[rang - 1] if rang > 0 else None
        suivant = jours[rang + 1] if rang + 1 < len(jours) else None

        photos_du_jour = list(
            jour.photos.filter(visible=True).order_by("ordre", "prise_le", "id").prefetch_related("rendus")
        )
        voisins = _charger_photos([v.photo_id for v in (precedent, suivant) if v])
        contexte = {
            "photos_du_jour": photos_du_jour,
            "photos": voisins,
            "precedent": precedent,
            "suivant": suivant,
            "fuseau": fuseau(jour.voyage),
        }
        return Response(JourDetailSerializer(jour, context=contexte).data)


class PhotosDuVoyageView(ListAPIView):
    """GET /api/voyages/<slug>/photos/ : photos visibles, dans l'ordre du voyage."""

    serializer_class = PhotoSerializer

    def get_queryset(self):
        voyage = get_object_or_404(Voyage, slug=self.kwargs["slug"])
        return (
            Photo.objects.filter(jour__voyage=voyage, visible=True)
            .select_related("jour")
            .prefetch_related("rendus")
        )
