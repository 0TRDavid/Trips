"""Qui peut lire l'API ? Un seul réglage, `API_ACCES` (variable d'environnement).

- « prive-reseau » (v1) : tout le monde. Le site n'est joignable que par
  Tailscale, c'est le réseau qui protège.
- « connecte » : il faut une session Django (connexion à l'admin aujourd'hui,
  une page de connexion du front plus tard). Le front est servi sur la même
  origine que l'API, le cookie de session suffit.

Dans tous les cas, l'API est en lecture seule : les vues n'acceptent que GET.
Le mode « public » (lecture seule sur internet, voyages publiés seulement)
est décrit dans docs/decisions.md et sera ajouté le jour de l'ouverture.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.permissions import SAFE_METHODS, BasePermission

MODES = ("prive-reseau", "connecte")


class LectureAPI(BasePermission):
    def has_permission(self, request, view):
        if request.method not in SAFE_METHODS:
            return False
        mode = settings.API_ACCES
        if mode == "prive-reseau":
            return True
        if mode == "connecte":
            return bool(request.user and request.user.is_authenticated)
        raise ImproperlyConfigured(f"API_ACCES inconnu : {mode!r} (attendu : {', '.join(MODES)})")
