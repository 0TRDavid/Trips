"""Voyage, Jour et Photo : le cœur du carnet.

Les dates de prise de vue sont stockées en UTC ; le regroupement par jour et
l'affichage se font dans le fuseau horaire du voyage.
"""

from django.conf import settings
from django.db import models


class Voyage(models.Model):
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voyages"
    )
    titre = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    # Chemin du dossier dans Nextcloud : permet de retrouver le voyage à la relance.
    dossier_nextcloud = models.CharField(max_length=1000, unique=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    # Nom IANA, par exemple « Asia/Tokyo ».
    fuseau_horaire = models.CharField(max_length=64)
    # Horloge des appareils qui n'enregistrent pas de décalage horaire, quand elle
    # n'était pas à l'heure du voyage : {"Canon EOS 100D": "UTC"}.
    horloges_appareils = models.JSONField(default=dict, blank=True)
    couverture = models.ForeignKey(
        "Photo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    recit_intro = models.TextField(blank=True, help_text="Markdown")

    class Meta:
        ordering = ["-date_debut"]

    def __str__(self):
        return self.titre


class Jour(models.Model):
    voyage = models.ForeignKey(Voyage, on_delete=models.CASCADE, related_name="jours")
    date = models.DateField(help_text="Date locale, dans le fuseau du voyage")
    titre = models.CharField(max_length=200, blank=True)
    recit = models.TextField(blank=True, help_text="Markdown")
    lieu = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["voyage", "date"]
        constraints = [
            models.UniqueConstraint(fields=["voyage", "date"], name="jour_unique_par_voyage")
        ]

    def __str__(self):
        return f"{self.voyage} — {self.date}"


class Photo(models.Model):
    jour = models.ForeignKey(Jour, on_delete=models.CASCADE, related_name="photos")
    chemin_nextcloud = models.CharField(max_length=1000, unique=True)
    # L'etag Nextcloud change quand le fichier change : sert à éviter les réimports.
    etag = models.CharField(max_length=200)
    prise_le = models.DateTimeField(help_text="UTC")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    appareil = models.CharField(max_length=200, blank=True)
    orientation = models.PositiveSmallIntegerField(null=True, blank=True)
    legende = models.TextField(blank=True)
    ordre = models.IntegerField(default=0)
    favori = models.BooleanField(default=False)
    visible = models.BooleanField(default=True)

    class Meta:
        ordering = ["jour", "ordre", "prise_le"]

    def __str__(self):
        return self.chemin_nextcloud.rsplit("/", 1)[-1]
