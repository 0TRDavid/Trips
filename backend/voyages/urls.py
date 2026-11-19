from django.urls import path, register_converter

from .views import JourView, PhotosDuVoyageView, VoyagesView, VoyageView


class DateIso:
    """AAAA-MM-JJ dans l'URL ; la vue vérifie que la date existe (sinon 404)."""

    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, valeur):
        return valeur

    def to_url(self, valeur):
        return str(valeur)


register_converter(DateIso, "date_iso")

urlpatterns = [
    path("voyages/", VoyagesView.as_view(), name="voyages"),
    path("voyages/<slug:slug>/", VoyageView.as_view(), name="voyage"),
    path("voyages/<slug:slug>/jours/<date_iso:date_iso>/", JourView.as_view(), name="jour"),
    path("voyages/<slug:slug>/photos/", PhotosDuVoyageView.as_view(), name="photos-du-voyage"),
]
