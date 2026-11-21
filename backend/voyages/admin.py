"""Admin Django : l'endroit où l'on écrit le carnet.

- Voyage : titre, dates, fuseau, récit d'introduction, couverture choisie dans
  une grille de miniatures ; la liste de ses jours, avec ce qu'il reste à écrire.
- Jour : titre, lieu, récit (éditeur Markdown avec aperçu rendu par le serveur),
  photos en ligne avec miniature, légende, favori, visible, et ordre réglé par
  glisser-déposer (django-admin-sortable2).
- Photo : liste pour chercher et corriger.
- Action « Régénérer les rendus » sur une sélection de voyages, jours ou photos.
- Écran « Compléter les médias » (admin_completion.py) : date et position des
  médias qui n'en ont pas, sur une carte.

Voyages, jours et photos naissent de l'import Nextcloud : on ne les crée pas
ici, et on ne supprime ni voyage ni jour (leurs récits n'existent nulle part
ailleurs).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from adminsortable2.admin import SortableAdminBase, SortableTabularInline
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.http import urlencode

from . import admin_completion
from .markdown import rendre_markdown
from .models import Jour, Photo, Voyage
from .widgets import ChoixCouverture, EditeurMarkdown, url_miniature

admin.site.site_header = "Carnet de voyages"
admin.site.site_title = "Carnet de voyages"
admin.site.index_title = "Écrire le carnet"

RECIT_REMPLI = Q(recit__regex=r"\S")  # au moins un caractère non blanc


# --- Utilitaires ---------------------------------------------------------------


def miniature(photo, classe="miniature-admin"):
    url = url_miniature(photo) if photo else None
    if not url:
        return "—"
    return format_html(
        '<img src="{}" class="{}" alt="" loading="lazy" style="background:{}">', url, classe, photo.couleur or "#888"
    )


def lancer_regeneration(photos_ids: list[int]) -> subprocess.Popen:
    """Lance `generer_rendus --force` en arrière-plan sur ces photos.

    Un voyage entier prend ~45 s : trop pour une requête HTTP. La commande
    tourne dans son propre processus (sa sortie va dans `docker compose logs
    backend`) et garde son parallélisme, sans forker le serveur web.
    """
    commande = [
        sys.executable, str(Path(settings.BASE_DIR) / "manage.py"),
        "generer_rendus", "--force", "--photos", ",".join(map(str, sorted(photos_ids))),
    ]
    return subprocess.Popen(commande, start_new_session=True, stdin=subprocess.DEVNULL)


def _action_regenerer(modeladmin, request, photos):
    ids = list(photos.values_list("id", flat=True))
    if not ids:
        modeladmin.message_user(request, "Aucune photo dans la sélection.", messages.WARNING)
        return
    lancer_regeneration(ids)
    modeladmin.message_user(
        request,
        f"Régénération de {len(ids)} photo{'s' if len(ids) > 1 else ''} lancée en arrière-plan "
        "(suivi : docker compose logs -f backend).",
        messages.SUCCESS,
    )


@admin.action(description="Régénérer les rendus des photos sélectionnées")
def regenerer_photos(modeladmin, request, queryset):
    _action_regenerer(modeladmin, request, Photo.objects.filter(id__in=queryset.values("id")))


@admin.action(description="Régénérer les rendus des jours sélectionnés")
def regenerer_jours(modeladmin, request, queryset):
    _action_regenerer(modeladmin, request, Photo.objects.filter(jour__in=queryset.values("id")))


@admin.action(description="Régénérer les rendus des voyages sélectionnés")
def regenerer_voyages(modeladmin, request, queryset):
    _action_regenerer(modeladmin, request, Photo.objects.filter(jour__voyage__in=queryset.values("id")))


class RecitRempliFiltre(admin.SimpleListFilter):
    title = "récit"
    parameter_name = "recit"

    def lookups(self, request, model_admin):
        return [("oui", "Écrit"), ("non", "À écrire")]

    def queryset(self, request, queryset):
        if self.value() == "oui":
            return queryset.filter(RECIT_REMPLI)
        if self.value() == "non":
            return queryset.exclude(RECIT_REMPLI)
        return queryset


def _jours_avec_comptes(queryset):
    return queryset.annotate(
        nb_photos=Count("photos"),
        nb_masquees=Count("photos", filter=Q(photos__visible=False)),
        recit_ecrit=Count("id", filter=RECIT_REMPLI),
    )


def _afficher_nb_photos(jour):
    if jour.nb_masquees:
        return f"{jour.nb_photos} (dont {jour.nb_masquees} masquée{'s' if jour.nb_masquees > 1 else ''})"
    return jour.nb_photos


# --- Voyage ----------------------------------------------------------------------


class JourEnLigne(admin.TabularInline):
    """Les jours du voyage, en lecture seule : ce qu'il reste à écrire."""

    model = Jour
    verbose_name_plural = "jours"
    fields = ["jour", "titre", "photos", "recit_ecrit"]
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return _jours_avec_comptes(super().get_queryset(request)).order_by("date")

    @admin.display(description="date")
    def jour(self, jour):
        url = reverse("admin:voyages_jour_change", args=[jour.pk])
        return format_html('<a href="{}">{}</a>', url, jour.date.strftime("%d/%m/%Y"))

    @admin.display(description="photos")
    def photos(self, jour):
        return _afficher_nb_photos(jour)

    @admin.display(description="récit écrit", boolean=True)
    def recit_ecrit(self, jour):
        return bool(jour.recit_ecrit)


def _fins_de_ligne_unix(texte: str) -> str:
    """Le navigateur envoie des \r\n : on stocke des \n (export Markdown propre)."""
    return texte.replace("\r\n", "\n").replace("\r", "\n")


class VoyageForm(forms.ModelForm):
    class Meta:
        model = Voyage
        fields = "__all__"
        widgets = {"recit_intro": EditeurMarkdown()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        champ = self.fields.get("couverture")
        if champ is not None:
            # Seulement les photos de ce voyage, avec de quoi afficher leur miniature.
            champ.queryset = (
                Photo.objects.filter(jour__voyage=self.instance.pk)
                .select_related("jour")
                .prefetch_related("rendus")
                .order_by("jour__date", "ordre", "prise_le")
            )
            champ.empty_label = "Automatique"
            champ.help_text = "Si aucune n'est choisie : le premier favori du voyage, sinon sa première photo."

    def clean_recit_intro(self):
        return _fins_de_ligne_unix(self.cleaned_data["recit_intro"])

    def clean_fuseau_horaire(self):
        valeur = self.cleaned_data["fuseau_horaire"].strip()
        try:
            ZoneInfo(valeur)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError("Fuseau inconnu : utiliser un nom IANA, par exemple Asia/Tokyo.") from None
        return valeur


@admin.register(Voyage)
class VoyageAdmin(admin.ModelAdmin):
    form = VoyageForm
    list_display = ["titre", "date_debut", "date_fin", "jours_a_ecrire", "lien_jours"]
    readonly_fields = ["apercu_couverture", "auteur", "dossier_nextcloud", "horloges_appareils", "lien_jours"]
    fieldsets = [
        (None, {"fields": ["titre", "slug", ("date_debut", "date_fin"), "fuseau_horaire", "lien_jours"]}),
        ("Couverture", {"fields": ["apercu_couverture", "couverture"]}),
        ("Récit d'introduction", {"fields": ["recit_intro"]}),
        ("Import", {
            "classes": ["collapse"],
            "fields": ["auteur", "dossier_nextcloud", "horloges_appareils"],
            "description": "Gérés par la commande import_voyage. Changer le fuseau ici ne regroupe pas "
                           "les photos par jour : il sert à l'affichage des heures.",
        }),
    ]
    inlines = [JourEnLigne]
    actions = [regenerer_voyages]

    def has_add_permission(self, request):
        return False  # un voyage naît d'un import Nextcloud

    def has_delete_permission(self, request, obj=None):
        return False  # les récits n'existent nulle part ailleurs

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related("couverture")
            .prefetch_related("couverture__rendus")
            .annotate(
                nb_jours=Count("jours", distinct=True),
                nb_ecrits=Count("jours", filter=Q(jours__recit__regex=r"\S"), distinct=True),
            )
        )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "couverture":
            # Grille de miniatures, sans l'enveloppe « ajouter / modifier » de l'admin
            # (inutile ici). Le queryset est restreint au voyage dans VoyageForm.
            return db_field.formfield(widget=ChoixCouverture(), required=False)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_urls(self):
        apercu = path(
            "apercu-markdown/", self.admin_site.admin_view(self.apercu_markdown), name="voyages_apercu_markdown"
        )
        return [apercu, *super().get_urls()]

    def apercu_markdown(self, request):
        """POST texte → {"html": …} : l'aperçu de l'éditeur, rendu comme sur le site."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        return JsonResponse({"html": rendre_markdown(request.POST.get("texte", ""))})

    @admin.display(description="récits écrits")
    def jours_a_ecrire(self, voyage):
        return f"{voyage.nb_ecrits} / {voyage.nb_jours} jours"

    @admin.display(description="jours")
    def lien_jours(self, voyage):
        if not voyage.pk:
            return "—"
        url = reverse("admin:voyages_jour_changelist") + "?" + urlencode({"voyage__id__exact": voyage.pk})
        return format_html('<a href="{}">Voir les jours de ce voyage</a>', url)

    @admin.display(description="couverture actuelle")
    def apercu_couverture(self, voyage):
        photo = voyage.couverture
        if photo is None:
            return "Automatique (aucune photo choisie)"
        return miniature(photo, "couverture-actuelle")


# --- Jour ------------------------------------------------------------------------


class PhotoEnLigne(SortableTabularInline):
    model = Photo
    ordering = ["ordre", "prise_le"]  # « ordre » en premier : c'est lui que le glisser-déposer règle
    fields = ["apercu", "heure", "legende", "favori", "visible"]
    readonly_fields = ["apercu", "heure"]
    extra = 0
    can_delete = False
    formfield_overrides = {
        Photo._meta.get_field("legende").__class__: {"widget": forms.Textarea(attrs={"rows": 2, "cols": 50})},
    }

    def has_add_permission(self, request, obj=None):
        return False  # les photos viennent de Nextcloud

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("jour__voyage").prefetch_related("rendus")

    @admin.display(description="photo")
    def apercu(self, photo):
        return miniature(photo)

    @admin.display(description="heure locale")
    def heure(self, photo):
        local = photo.prise_le.astimezone(ZoneInfo(photo.jour.voyage.fuseau_horaire))
        type_ = "" if photo.type == Photo.Type.PHOTO else f" · {photo.get_type_display()}"
        return format_html("{}<br><small>{}{}</small>", local.strftime("%H:%M"), photo, type_)


class JourForm(forms.ModelForm):
    class Meta:
        model = Jour
        fields = ["titre", "lieu", "recit"]
        widgets = {"recit": EditeurMarkdown()}

    def clean_recit(self):
        return _fins_de_ligne_unix(self.cleaned_data["recit"])


@admin.register(Jour)
class JourAdmin(SortableAdminBase, admin.ModelAdmin):
    form = JourForm
    change_form_template = "admin/voyages/jour/change_form.html"
    list_display = ["date", "titre_ou_vide", "voyage", "photos", "recit_ecrit"]
    list_display_links = ["date", "titre_ou_vide"]
    list_filter = ["voyage", RecitRempliFiltre]
    list_select_related = ["voyage"]
    search_fields = ["titre", "lieu", "recit"]
    ordering = ["voyage", "date"]
    list_per_page = 100
    readonly_fields = ["voyage", "date"]
    fields = [("voyage", "date"), "titre", "lieu", "recit"]
    inlines = [PhotoEnLigne]
    actions = [regenerer_jours]

    def has_add_permission(self, request):
        return False  # un jour naît d'un import Nextcloud

    def has_delete_permission(self, request, obj=None):
        return False  # son récit n'existe nulle part ailleurs

    def get_queryset(self, request):
        return _jours_avec_comptes(super().get_queryset(request))

    @admin.display(description="titre", ordering="titre")
    def titre_ou_vide(self, jour):
        return jour.titre or "(sans titre)"

    @admin.display(description="photos", ordering="nb_photos")
    def photos(self, jour):
        return _afficher_nb_photos(jour)

    @admin.display(description="récit écrit", boolean=True, ordering="recit_ecrit")
    def recit_ecrit(self, jour):
        return bool(jour.recit_ecrit)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """Ajoute les liens vers le jour précédent et le jour suivant du même voyage."""
        extra_context = extra_context or {}
        jour = self.get_object(request, object_id)
        if jour is not None:
            voisins = Jour.objects.filter(voyage_id=jour.voyage_id)
            precedent = voisins.filter(date__lt=jour.date).order_by("-date").first()
            suivant = voisins.filter(date__gt=jour.date).order_by("date").first()
            extra_context["jour_precedent"] = precedent
            extra_context["jour_suivant"] = suivant
        return super().change_view(request, object_id, form_url, extra_context)


# --- Photo -----------------------------------------------------------------------


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ["apercu", "nom", "type", "jour", "prise_le", "photographe", "favori", "visible", "rendus_a_jour"]
    list_display_links = ["apercu", "nom"]
    list_editable = ["favori", "visible"]
    list_filter = [
        "jour__voyage", "type", "photographe", "visible", "favori", "source_date", "date_a_confirmer",
        "source_position", "appareil",
    ]
    list_select_related = ["jour__voyage"]
    search_fields = ["legende", "chemin_nextcloud"]
    date_hierarchy = "prise_le"
    list_per_page = 50
    fields = [
        "apercu_grand", "apercu_video", "legende", ("favori", "visible"), ("type", "duree"), "jour", "prise_le",
        ("source_date", "date_a_confirmer"), ("latitude", "longitude", "source_position"),
        "photographe", "appareil", ("largeur", "hauteur", "couleur"), "chemin_nextcloud",
    ]
    readonly_fields = [
        "apercu_grand", "apercu_video", "type", "duree", "jour", "prise_le", "photographe", "appareil",
        "largeur", "hauteur", "couleur", "chemin_nextcloud",
        "source_date", "date_a_confirmer", "latitude", "longitude", "source_position",
    ]
    actions = [regenerer_photos]
    change_list_template = "admin/voyages/photo/change_list.html"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        return [*admin_completion.urls(self.admin_site), *super().get_urls()]

    def has_delete_permission(self, request, obj=None):
        return False  # une photo disparue de Nextcloud est signalée par l'import, pas supprimée ici

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("rendus")

    @admin.display(description="photo")
    def apercu(self, photo):
        return miniature(photo, "miniature-admin miniature-admin--petite")

    @admin.display(description="aperçu")
    def apercu_grand(self, photo):
        return miniature(photo, "couverture-actuelle")

    @admin.display(description="vidéo")
    def apercu_video(self, photo):
        """Lecteur de la plus petite vidéo (photo animée : en boucle et sans son)."""
        rendus = sorted((r for r in photo.rendus.all() if r.format == "mp4"), key=lambda r: r.largeur)
        if not rendus:
            return "—" if photo.type == Photo.Type.PHOTO else "rendus vidéo pas encore générés"
        animee = photo.type == Photo.Type.ANIMEE
        return format_html(
            '<video src="{}" class="couverture-actuelle" controls preload="metadata" playsinline{}></video>',
            settings.MEDIA_URL + rendus[0].fichier,
            mark_safe(" muted loop autoplay") if animee else "",
        )

    @admin.display(description="fichier", ordering="chemin_nextcloud")
    def nom(self, photo):
        return str(photo)

    @admin.display(description="rendus à jour", boolean=True)
    def rendus_a_jour(self, photo):
        images = bool(photo.rendus_etag) and photo.rendus_etag == photo.etag
        videos = photo.type == Photo.Type.PHOTO or photo.videos_etag == photo.etag
        return images and videos

    class Media:
        css = {"all": ["voyages/admin.css"]}
