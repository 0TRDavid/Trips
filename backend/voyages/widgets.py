"""Widgets de l'admin : éditeur Markdown avec aperçu, choix de la couverture."""

from django import forms
from django.conf import settings
from django.urls import reverse_lazy


class EditeurMarkdown(forms.Textarea):
    """Zone de texte enrichie par EasyMDE (copié dans static/, pas de CDN).

    L'aperçu n'utilise pas le moteur Markdown d'EasyMDE : il demande le rendu au
    serveur (voyages.markdown.rendre_markdown), donc il est identique au site.
    """

    def __init__(self, attrs=None):
        attrs = {"class": "editeur-markdown", "rows": 18, **(attrs or {})}
        attrs["data-apercu-url"] = reverse_lazy("admin:voyages_apercu_markdown")
        super().__init__(attrs)

    class Media:
        css = {"all": ["voyages/easymde/easymde.min.css", "voyages/admin.css"]}
        js = ["voyages/easymde/easymde.min.js", "voyages/editeur.js"]


def url_miniature(photo) -> str | None:
    """URL du rendu « miniature » ; utilise le prefetch de `rendus` s'il existe."""
    for rendu in photo.rendus.all():
        if rendu.taille == "miniature":
            return settings.MEDIA_URL + rendu.fichier
    return None


class ChoixCouverture(forms.RadioSelect):
    """Boutons radio présentés en grille de miniatures.

    Le queryset du champ doit précharger `rendus` et `jour` (sinon une requête
    par photo).
    """

    template_name = "voyages/widgets/choix_couverture.html"
    option_template_name = "voyages/widgets/choix_couverture_option.html"

    class Media:
        css = {"all": ["voyages/admin.css"]}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        photo = getattr(value, "instance", None)  # ModelChoiceIteratorValue ; None pour « aucune »
        option["miniature"] = url_miniature(photo) if photo else None
        option["photo"] = photo
        return option
