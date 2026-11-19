"""python manage.py import_voyage "<dossier Nextcloud>" [--fuseau Asia/Tokyo] ..."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from voyages.importation import ImportErreur, importer_voyage
from voyages.nextcloud import ClientWebDAV, NextcloudErreur


def creer_client() -> ClientWebDAV:
    return ClientWebDAV(
        settings.NEXTCLOUD_URL, settings.NEXTCLOUD_USER, settings.NEXTCLOUD_PASSWORD
    )


class Command(BaseCommand):
    help = "Importe (ou réimporte) un dossier de voyage depuis Nextcloud, sans copier les originaux."

    def add_arguments(self, parser):
        parser.add_argument("dossier", help="Chemin du dossier, depuis la racine Nextcloud de l'utilisateur")
        parser.add_argument("--fuseau", help="Fuseau IANA du voyage (obligatoire au premier import), ex. Asia/Tokyo")
        parser.add_argument("--titre", help="Titre du voyage (par défaut : nom du dossier)")
        parser.add_argument("--auteur", help="Nom d'utilisateur de l'auteur (par défaut : le seul superuser)")
        parser.add_argument(
            "--horloge", action="append", default=[], metavar="APPAREIL=FUSEAU",
            help="Horloge d'un appareil sans décalage EXIF, mémorisée sur le voyage "
                 "(ex. \"Canon EOS 100D=UTC\"). Répétable.",
        )
        parser.add_argument("--limite", type=int, help="N'importe que les N premières photos (test)")
        parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait fait, sans rien écrire ni télécharger")

    def handle(self, *args, **options):
        try:
            rapport = importer_voyage(
                creer_client(),
                options["dossier"],
                fuseau=options["fuseau"],
                auteur=self._auteur(options["auteur"]),
                titre=options["titre"],
                horloges=self._horloges(options["horloge"]),
                limite=options["limite"],
                dry_run=options["dry_run"],
                progression=self._progression,
            )
        except (ImportErreur, NextcloudErreur) as exc:
            raise CommandError(str(exc)) from None
        self._afficher(rapport)

    def _horloges(self, valeurs):
        horloges = {}
        for valeur in valeurs:
            appareil, egal, fuseau = valeur.rpartition("=")
            if not egal or not appareil.strip() or not fuseau.strip():
                raise CommandError(f"--horloge attend APPAREIL=FUSEAU, reçu « {valeur} »")
            horloges[appareil.strip()] = fuseau.strip()
        return horloges

    def _auteur(self, nom):
        User = get_user_model()
        if nom:
            try:
                return User.objects.get(username=nom)
            except User.DoesNotExist:
                raise CommandError(f"Utilisateur inconnu : « {nom} »") from None
        superusers = list(User.objects.filter(is_superuser=True)[:2])
        # Ambiguïté ou absence : l'import refusera seulement s'il doit créer le voyage.
        return superusers[0] if len(superusers) == 1 else None

    def _progression(self, i, total, chemin):
        if i == 1 or i % 25 == 0 or i == total:
            self.stdout.write(f"  {i}/{total}  {chemin.rsplit('/', 1)[-1]}")

    def _afficher(self, r):
        w = self.stdout.write
        w("")
        w(self.style.MIGRATE_HEADING("Simulation (--dry-run) : rien n'a été écrit" if r.dry_run else "Import terminé"))
        if r.voyage:
            w(f"Voyage : {r.voyage.titre} ({r.voyage.date_debut} → {r.voyage.date_fin}, {r.voyage.fuseau_horaire})")
            for appareil, fuseau in r.voyage.horloges_appareils.items():
                w(f"  horloge {appareil} : {fuseau}")
        w(f"Images dans Nextcloud : {r.images_nextcloud}")
        w(f"Photos en base        : {r.photos_en_base}")
        w(f"  créées {r.creees} · mises à jour {r.mises_a_jour} · inchangées {r.inchangees}")
        if r.ignores:
            detail = ", ".join(f"{ext} : {n}" for ext, n in sorted(r.ignores.items()))
            w(f"Fichiers ignorés      : {sum(r.ignores.values())} ({detail})")
        if r.sans_date:
            w(self.style.WARNING(f"Sans date EXIF (date du fichier, masquées) : {len(r.sans_date)}"))
            for chemin in r.sans_date:
                w(f"  - {chemin}")
        if r.disparues:
            w(self.style.WARNING(f"En base mais absentes de Nextcloud (conservées) : {len(r.disparues)}"))
            for chemin in r.disparues:
                w(f"  - {chemin}")
        if not r.dry_run:
            if r.limite:
                w(f"(--limite {r.limite} : écart normal, relance sans --limite pour tout importer)")
            elif r.images_nextcloud == r.photos_en_base:
                w(self.style.SUCCESS(f"✔ Nextcloud et la base concordent : {r.photos_en_base} photos"))
            else:
                w(self.style.WARNING(f"≠ Écart : {r.images_nextcloud} dans Nextcloud, {r.photos_en_base} en base"))
