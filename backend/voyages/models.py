"""Voyage, Jour et Photo : le cœur du carnet.

Les dates de prise de vue sont stockées en UTC ; le regroupement par jour et
l'affichage se font dans le fuseau horaire du voyage.
"""

from django.conf import settings
from django.db import models


class Voyage(models.Model):
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="voyages", verbose_name="auteur"
    )
    titre = models.CharField("titre", max_length=200)
    slug = models.SlugField("slug (adresse)", max_length=200, unique=True)
    # Chemin du dossier dans Nextcloud : permet de retrouver le voyage à la relance.
    dossier_nextcloud = models.CharField("dossier Nextcloud", max_length=1000, unique=True)
    date_debut = models.DateField("début", null=True, blank=True)
    date_fin = models.DateField("fin", null=True, blank=True)
    # Nom IANA, par exemple « Asia/Tokyo ».
    fuseau_horaire = models.CharField("fuseau horaire", max_length=64, help_text="Nom IANA, par exemple Asia/Tokyo")
    # Horloge des appareils qui n'enregistrent pas de décalage horaire, quand elle
    # n'était pas à l'heure du voyage : {"Canon EOS 100D": "UTC"}.
    horloges_appareils = models.JSONField("horloges des appareils", default=dict, blank=True)
    couverture = models.ForeignKey(
        "Photo", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        verbose_name="photo de couverture",
    )
    recit_intro = models.TextField("récit d'introduction", blank=True, help_text="Markdown")

    class Meta:
        ordering = ["-date_debut"]
        verbose_name = "voyage"

    def __str__(self):
        return self.titre


class Jour(models.Model):
    voyage = models.ForeignKey(
        Voyage, on_delete=models.CASCADE, related_name="jours", verbose_name="voyage"
    )
    date = models.DateField("date", help_text="Date locale, dans le fuseau du voyage")
    titre = models.CharField("titre", max_length=200, blank=True)
    recit = models.TextField("récit", blank=True, help_text="Markdown")
    lieu = models.CharField("lieu principal", max_length=200, blank=True)

    class Meta:
        ordering = ["voyage", "date"]
        verbose_name = "jour"
        constraints = [
            models.UniqueConstraint(fields=["voyage", "date"], name="jour_unique_par_voyage")
        ]

    def __str__(self):
        return f"{self.voyage} — {self.date}"


class Photo(models.Model):
    jour = models.ForeignKey(Jour, on_delete=models.CASCADE, related_name="photos", verbose_name="jour")
    chemin_nextcloud = models.CharField("chemin Nextcloud", max_length=1000, unique=True)
    # L'etag Nextcloud change quand le fichier change : sert à éviter les réimports.
    etag = models.CharField("etag", max_length=200)
    prise_le = models.DateTimeField("prise le", help_text="UTC")
    latitude = models.FloatField("latitude", null=True, blank=True)
    longitude = models.FloatField("longitude", null=True, blank=True)
    altitude = models.FloatField("altitude", null=True, blank=True)
    appareil = models.CharField("appareil", max_length=200, blank=True)
    orientation = models.PositiveSmallIntegerField("orientation", null=True, blank=True)
    legende = models.TextField("légende", blank=True)
    # Position dans le jour (1, 2, 3…), réglée par glisser-déposer dans l'admin.
    ordre = models.IntegerField("ordre", default=0)
    favori = models.BooleanField("favori", default=False)
    visible = models.BooleanField("visible", default=True)
    # Calculés à la génération des rendus : servent à réserver la place et à
    # animer la page avant que l'image soit chargée.
    largeur = models.PositiveIntegerField("largeur", null=True, blank=True, help_text="Orientation appliquée")
    hauteur = models.PositiveIntegerField("hauteur", null=True, blank=True, help_text="Orientation appliquée")
    couleur = models.CharField("couleur", max_length=7, blank=True, help_text="Couleur dominante, #rrggbb")
    placeholder = models.CharField("placeholder", max_length=100, blank=True, help_text="ThumbHash en base64")
    # Etag de l'original pour lequel les rendus ont été générés (vide : à faire).
    rendus_etag = models.CharField("etag des rendus", max_length=200, blank=True)

    class Meta:
        ordering = ["jour", "ordre", "prise_le"]
        verbose_name = "photo"

    def __str__(self):
        return self.chemin_nextcloud.rsplit("/", 1)[-1]


class Rendu(models.Model):
    """Version web d'une photo, sans métadonnées, dans le cache (MEDIA_ROOT)."""

    class Taille(models.TextChoices):
        MINIATURE = "miniature"
        MOYENNE = "moyenne"
        GRANDE = "grande"

    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="rendus", verbose_name="photo")
    taille = models.CharField(max_length=20, choices=Taille.choices)
    format = models.CharField(max_length=10, default="webp")
    largeur = models.PositiveIntegerField()
    hauteur = models.PositiveIntegerField()
    octets = models.PositiveIntegerField()
    # Chemin relatif à MEDIA_ROOT : « rendus/42/3f9a…-moyenne.webp ».
    fichier = models.CharField(max_length=300)

    class Meta:
        ordering = ["photo", "largeur"]
        verbose_name = "rendu"
        constraints = [
            models.UniqueConstraint(fields=["photo", "taille"], name="rendu_unique_par_taille")
        ]

    def __str__(self):
        return self.fichier
