"""Sérialisation pour le front (lecture seule).

Aucune donnée sensible n'est exposée : ni chemin Nextcloud, ni etag, ni
coordonnées par photo. Seul le tracé allégé du voyage contient des positions.

Les récits sont renvoyés deux fois : en Markdown (la source) et en HTML
nettoyé, produit par `voyages.markdown.rendre_markdown`, le même moteur que
l'aperçu de l'admin.

Chaque voyage et chaque jour porte sa `palette` (voyages/palette.py), tirée
des couleurs vives de ses médias visibles, contrastes AA garantis.

Les serializers ne déclenchent aucune requête : les vues leur passent des
objets déjà chargés (annotations, prefetch, photos représentatives en contexte).
"""

from zoneinfo import ZoneInfo

from django.conf import settings
from rest_framework import serializers

from .markdown import rendre_markdown
from .models import Jour, Photo, Voyage
from .palette import palette
from .rendus import TAILLES
from .rendus_video import TAILLES_VIDEO


def _fichier(rendu) -> dict:
    # URL relative : elle passe par le même hôte que la page (proxy Vite, puis NPM).
    return {"url": settings.MEDIA_URL + rendu.fichier, "largeur": rendu.largeur, "hauteur": rendu.hauteur}


def _rendus(photo: Photo) -> dict:
    """Images WebP (la photo, ou l'aperçu d'une vidéo) :
    {"miniature": {"url": "/media/rendus/…", "largeur": 400, "hauteur": 267}, …}"""
    return {r.taille: _fichier(r) for r in photo.rendus.all() if r.taille in TAILLES}


def _videos(photo: Photo) -> dict:
    """Vidéos MP4 par petit côté visé : {"720": {...}, "1080": {...}} ; vide pour
    une photo. Filtré en Python sur les rendus déjà chargés : aucune requête."""
    return {
        str(TAILLES_VIDEO[r.taille]): _fichier(r)
        for r in photo.rendus.all() if r.taille in TAILLES_VIDEO
    }


class _MediaMixin(serializers.Serializer):
    """Ce qu'il faut pour lire un média : son type, sa durée, ses vidéos.
    L'aperçu (poster) d'une vidéo est dans `rendus`, comme une photo."""

    videos = serializers.SerializerMethodField()

    def get_videos(self, photo):
        return _videos(photo)


class PhotoSerializer(_MediaMixin, serializers.ModelSerializer):
    """Médias d'un voyage entier (GET /api/voyages/<slug>/photos/)."""

    jour = serializers.DateField(source="jour.date")
    rendus = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            "id", "type", "duree", "jour", "prise_le", "legende", "favori", "photographe",
            "largeur", "hauteur", "couleur", "placeholder", "rendus", "videos",
        ]

    def get_rendus(self, photo):
        return _rendus(photo)


class VignetteSerializer(serializers.ModelSerializer):
    """Le minimum pour afficher une image et l'animer avant son chargement."""

    rendus = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = ["id", "largeur", "hauteur", "couleur", "placeholder", "rendus"]

    def get_rendus(self, photo):
        return _rendus(photo)


class PhotoDuJourSerializer(_MediaMixin, VignetteSerializer):
    """Photo dans la page d'un jour : `prise_le` porte le décalage du voyage
    (« 2025-06-01T14:03:00+09:00 ») : même instant que l'UTC stocké, mais
    directement affichable en heure locale."""

    prise_le = serializers.SerializerMethodField()

    class Meta(VignetteSerializer.Meta):
        fields = VignetteSerializer.Meta.fields + [
            "type", "duree", "videos", "prise_le", "legende", "favori", "photographe",
        ]

    def get_prise_le(self, photo):
        return photo.prise_le.astimezone(self.context["fuseau"]).isoformat()


def _vignette(photos: dict[int, Photo], photo_id: int | None):
    photo = photos.get(photo_id)
    return VignetteSerializer(photo).data if photo else None


class JourResumeSerializer(serializers.ModelSerializer):
    """Un jour dans la timeline d'un voyage. Attend les annotations
    `nb_photos` et `photo_id`, et `context["photos"]` ({id: Photo})."""

    nb_photos = serializers.IntegerField()
    recit_rempli = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    palette = serializers.SerializerMethodField()

    class Meta:
        model = Jour
        fields = ["date", "titre", "lieu", "nb_photos", "recit_rempli", "photo", "palette"]

    def get_palette(self, jour):
        return self.context["palettes_jours"].get(jour.date) or palette([])

    def get_recit_rempli(self, jour):
        return bool(jour.recit.strip())

    def get_photo(self, jour):
        return _vignette(self.context["photos"], jour.photo_id)


class VoisinSerializer(serializers.ModelSerializer):
    """Jour précédent ou suivant : de quoi préparer la transition animée."""

    photo = serializers.SerializerMethodField()

    class Meta:
        model = Jour
        fields = ["date", "titre", "photo"]

    def get_photo(self, jour):
        return _vignette(self.context["photos"], jour.photo_id)


class VoyageResumeSerializer(serializers.ModelSerializer):
    """Un voyage sur la page d'accueil. Attend les annotations `nb_jours`,
    `nb_photos` et `couverture_effective_id`, `context["photos"]` et
    `context["palettes"]` ({voyage_id: palette})."""

    nb_jours = serializers.IntegerField()
    nb_photos = serializers.IntegerField()
    couverture = serializers.SerializerMethodField()
    palette = serializers.SerializerMethodField()

    class Meta:
        model = Voyage
        fields = [
            "slug", "titre", "date_debut", "date_fin", "fuseau_horaire", "nb_jours", "nb_photos",
            "couverture", "palette",
        ]

    def get_palette(self, voyage):
        return self.context["palettes"].get(voyage.id) or palette([])

    def get_couverture(self, voyage):
        return _vignette(self.context["photos"], voyage.couverture_effective_id)


class VoyageDetailSerializer(VoyageResumeSerializer):
    """Page d'un voyage. Attend en plus `context["jours"]` et `context["trace"]`."""

    recit_intro_html = serializers.SerializerMethodField()
    jours = serializers.SerializerMethodField()
    trace = serializers.SerializerMethodField()

    class Meta(VoyageResumeSerializer.Meta):
        fields = VoyageResumeSerializer.Meta.fields + ["recit_intro", "recit_intro_html", "jours", "trace"]

    def get_recit_intro_html(self, voyage):
        return rendre_markdown(voyage.recit_intro)

    def get_jours(self, voyage):
        return JourResumeSerializer(self.context["jours"], many=True, context=self.context).data

    def get_trace(self, voyage):
        return self.context["trace"]


class JourDetailSerializer(serializers.ModelSerializer):
    """Page d'un jour. Attend `context["photos_du_jour"]`, `context["precedent"]`,
    `context["suivant"]`, `context["photos"]` (vignettes des voisins),
    `context["fuseau"]` et `context["palette"]`."""

    voyage = serializers.SerializerMethodField()
    recit_html = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    precedent = serializers.SerializerMethodField()
    suivant = serializers.SerializerMethodField()

    class Meta:
        model = Jour
        fields = [
            "date", "titre", "lieu", "recit", "recit_html", "voyage", "photos", "precedent", "suivant", "palette",
        ]

    palette = serializers.SerializerMethodField()

    def get_palette(self, jour):
        return self.context["palette"]

    def get_voyage(self, jour):
        v = jour.voyage
        return {"slug": v.slug, "titre": v.titre, "fuseau_horaire": v.fuseau_horaire}

    def get_recit_html(self, jour):
        return rendre_markdown(jour.recit)

    def get_photos(self, jour):
        return PhotoDuJourSerializer(self.context["photos_du_jour"], many=True, context=self.context).data

    def _voisin(self, jour):
        return VoisinSerializer(jour, context=self.context).data if jour else None

    def get_precedent(self, jour):
        return self._voisin(self.context["precedent"])

    def get_suivant(self, jour):
        return self._voisin(self.context["suivant"])


def fuseau(voyage: Voyage) -> ZoneInfo:
    return ZoneInfo(voyage.fuseau_horaire)
