"""python manage.py import_voyage "<dossier Nextcloud>" [--fuseau Asia/Tokyo] ..."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from voyages.generation import generer_rendus, photos_a_traiter
from voyages.importation import ImportErreur, importer_voyage
from voyages.management.commands.generer_rendus import afficher_rapport_rendus
from voyages.nextcloud import NextcloudErreur, client_depuis_settings


def creer_client():
    return client_depuis_settings()


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
                 "(ex. \"Canon EOS 100D=UTC\"). Répétable. « nom de fichier=Europe/Paris » : "
                 "une vidéo nommée « AA-MM-JJ HH-MM-SS… » est datée par son nom, lu dans ce fuseau.",
        )
        parser.add_argument(
            "--ancien-dossier", metavar="DOSSIER",
            help="Le dossier du voyage a été renommé ou déplacé dans Nextcloud : son ancien chemin. "
                 "Le voyage, ses récits et ses photos sont conservés.",
        )
        parser.add_argument("--limite", type=int, help="N'importe que les N premières photos (test)")
        parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait fait, sans rien écrire ni télécharger")
        parser.add_argument("--sans-rendus", action="store_true", help="Ne génère pas les rendus web (voir generer_rendus)")

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
                ancien_dossier=options["ancien_dossier"],
                progression=self._progression,
            )
        except (ImportErreur, NextcloudErreur) as exc:
            raise CommandError(str(exc)) from None
        self._afficher(rapport)
        if not options["sans_rendus"]:
            self._rendus(rapport)

    def _rendus(self, rapport):
        if rapport.voyage is None:  # premier import simulé : rien en base
            self.stdout.write(f"Rendus web à générer : {rapport.creees}")
            return
        if rapport.dry_run:
            a_faire, _ = photos_a_traiter(rapport.voyage)
            self.stdout.write(f"Rendus web à générer : {len(a_faire) + rapport.creees + rapport.mises_a_jour} (au plus)")
            return
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Rendus web"))
        rapport_rendus = generer_rendus(
            fabrique_client=creer_client, voyage=rapport.voyage, progression=self._progression,
        )
        afficher_rapport_rendus(self, rapport_rendus)

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
            if r.renomme_depuis:
                verbe = "serait déplacé" if r.dry_run else "déplacé"
                w(f"  dossier {verbe} : « {r.renomme_depuis} » → « {r.dossier} »")
            for appareil, fuseau in r.voyage.horloges_appareils.items():
                w(f"  horloge {appareil} : {fuseau}")
        w(f"Médias dans Nextcloud : {r.images_nextcloud} (photos et vidéos)")
        w(f"Médias en base        : {r.photos_en_base}")
        if r.types:
            noms = {"photo": "photos", "animee": "photos animées", "video": "vidéos"}
            w("  dont " + " · ".join(f"{noms.get(t, t)} {n}" for t, n in sorted(r.types.items())))
        w(f"  créés {r.creees} · mis à jour {r.mises_a_jour} · inchangés {r.inchangees}")
        if r.reanalysees:
            w(f"  dont relus pour la nouvelle analyse (photos animées) : {r.reanalysees}")
        if r.deplacees:
            w(f"  dont déplacées dans Nextcloud (reconnues, non réimportées) : {r.deplacees}")
        if r.ignores:
            detail = ", ".join(f"{ext} : {n}" for ext, n in sorted(r.ignores.items()))
            w(f"Fichiers ignorés      : {sum(r.ignores.values())} ({detail})")
        if r.sans_date:
            w(self.style.WARNING(f"Sans date de prise de vue (date du fichier, masqués) : {len(r.sans_date)}"))
            for chemin in r.sans_date:
                w(f"  - {chemin}")
        if r.erreurs:
            w(self.style.WARNING(f"Illisibles (retentés à la prochaine relance) : {len(r.erreurs)}"))
            for chemin, message in r.erreurs:
                w(f"  - {chemin} : {message}")
        if r.disparues:
            w(self.style.WARNING(f"En base mais absentes de Nextcloud (conservées) : {len(r.disparues)}"))
            for chemin in r.disparues:
                w(f"  - {chemin}")
        if not r.dry_run:
            if r.limite:
                w(f"(--limite {r.limite} : écart normal, relance sans --limite pour tout importer)")
            elif r.images_nextcloud == r.photos_en_base:
                w(self.style.SUCCESS(f"✔ Nextcloud et la base concordent : {r.photos_en_base} médias"))
            else:
                w(self.style.WARNING(f"≠ Écart : {r.images_nextcloud} dans Nextcloud, {r.photos_en_base} en base"))
