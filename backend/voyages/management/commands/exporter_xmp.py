"""python manage.py exporter_xmp [--voyage <slug>] [--photos 1,2,3] [--dry-run]"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from voyages.export_xmp import ExportErreur, exporter, photos_avec_saisie
from voyages.models import Photo, Voyage
from voyages.nextcloud import NextcloudErreur, client_depuis_settings


def creer_client():
    return client_depuis_settings()


class Command(BaseCommand):
    help = (
        "Écrit dans le dossier d'export Nextcloud (NEXTCLOUD_DOSSIER_EXPORT) un sidecar XMP par média "
        "dont la date ou la position a été saisie à la main. Les originaux ne sont jamais modifiés."
    )

    def add_arguments(self, parser):
        parser.add_argument("--voyage", help="Slug du voyage (par défaut : tous)")
        parser.add_argument("--photos", help="Identifiants séparés par des virgules (lancé par l'écran Compléter)")
        parser.add_argument("--dry-run", action="store_true", help="Liste les sidecars à écrire, sans rien écrire")

    def handle(self, *args, **options):
        photos = Photo.objects.all()
        if options["voyage"]:
            if not Voyage.objects.filter(slug=options["voyage"]).exists():
                raise CommandError(f"Voyage inconnu : « {options['voyage']} »")
            photos = photos.filter(jour__voyage__slug=options["voyage"])
        if options["photos"]:
            try:
                ids = [int(i) for i in options["photos"].split(",") if i.strip()]
            except ValueError:
                raise CommandError("--photos attend des identifiants séparés par des virgules") from None
            photos = photos.filter(pk__in=ids)
        try:
            client = None if options["dry_run"] else creer_client()
            rapport = exporter(
                client, photos_avec_saisie(photos), settings.NEXTCLOUD_DOSSIER_EXPORT, dry_run=options["dry_run"]
            )
        except (ExportErreur, NextcloudErreur) as exc:
            raise CommandError(str(exc)) from None

        w, style = self.stdout.write, self.style
        verbe = "à écrire" if rapport.dry_run else "écrits"
        w(f"Sidecars XMP {verbe} : {len(rapport.ecrits)} · déjà à jour : {rapport.a_jour}")
        for chemin in rapport.ecrits[:20]:
            w(f"  - {chemin}")
        if len(rapport.ecrits) > 20:
            w(f"  … et {len(rapport.ecrits) - 20} autres")
        if rapport.erreurs:
            w(style.WARNING(f"Erreurs ({len(rapport.erreurs)}, retentées à la prochaine relance) :"))
            for chemin, message in rapport.erreurs:
                w(f"  - {chemin} : {message}")
        elif not rapport.dry_run:
            w(style.SUCCESS("✔ Sidecars XMP à jour"))
