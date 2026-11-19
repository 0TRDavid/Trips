"""Sérialisation des photos pour le front (lecture seule).

Aucune coordonnée GPS n'est exposée ici ; la carte de l'étape 5 décidera ce
qu'elle affiche.
"""

from django.conf import settings
from rest_framework import serializers

from .models import Photo


class PhotoSerializer(serializers.ModelSerializer):
    jour = serializers.DateField(source="jour.date")
    rendus = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "id", "jour", "prise_le", "legende", "favori",
            "largeur", "hauteur", "couleur", "placeholder", "rendus",
        ]

    def get_rendus(self, photo):
        # {"miniature": {"url": "/media/rendus/…", "largeur": 400, "hauteur": 267}, …}
        # URL relative : elle passe par le même hôte que la page (proxy Vite, puis NPM).
        return {
            rendu.taille: {
                "url": settings.MEDIA_URL + rendu.fichier,
                "largeur": rendu.largeur,
                "hauteur": rendu.hauteur,
            }
            for rendu in photo.rendus.all()
        }
