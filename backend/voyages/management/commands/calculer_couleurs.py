"""python manage.py calculer_couleurs [--voyage <slug>] [--force]

Couleurs vives des médias déjà rendus, lues dans leur miniature WebP du cache :
ni Nextcloud ni original. Les nouveaux médias les reçoivent à la génération
de leurs rendus ; cette commande sert à rattraper l'existant.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from PIL import Image

from voyages.models import Photo, Rendu, Voyage
from voyages.palette import couleurs_vives


class Command(BaseCommand):
    help = "Calcule les couleurs vives des médias à partir de leur miniature en cache."

    def add_arguments(self, parser):
        parser.add_argument("--voyage", help="Slug du voyage (par défaut : tous)")
        parser.add_argument("--force", action="store_true", help="Recalcule aussi les médias qui en ont déjà")

    def handle(self, *args, voyage=None, force=False, **options):
        photos = Photo.objects.all()
        if voyage:
            if not Voyage.objects.filter(slug=voyage).exists():
                raise CommandError(f"Voyage inconnu : « {voyage} »")
            photos = photos.filter(jour__voyage__slug=voyage)
        if not force:
            photos = photos.filter(couleurs=[])
        miniatures = dict(
            Rendu.objects.filter(photo__in=photos, taille="miniature").values_list("photo_id", "fichier")
        )

        calculees = sans_rendu = 0
        for photo in photos.only("id", "couleurs"):
            fichier = miniatures.get(photo.id)
            chemin = Path(settings.MEDIA_ROOT) / fichier if fichier else None
            if chemin is None or not chemin.exists():
                sans_rendu += 1
                continue
            with Image.open(chemin) as image:
                photo.couleurs = couleurs_vives(image)
            photo.save(update_fields=["couleurs"])
            calculees += 1

        self.stdout.write(f"Couleurs calculées : {calculees}")
        if sans_rendu:
            self.stdout.write(self.style.WARNING(f"Sans miniature en cache (generer_rendus d'abord) : {sans_rendu}"))
