"""python manage.py generer_rendus [--voyage <slug>] [--force] [--processus N]"""

from django.core.management.base import BaseCommand, CommandError

from voyages.generation import PROCESSUS_PAR_DEFAUT, generer_rendus
from voyages.models import Voyage
from voyages.nextcloud import NextcloudErreur, client_depuis_settings


def creer_client():
    return client_depuis_settings()


def _taille_lisible(octets: int) -> str:
    for unite in ("o", "Ko", "Mo", "Go"):
        if octets < 1024 or unite == "Go":
            return f"{octets:.0f} {unite}" if unite == "o" else f"{octets:.1f} {unite}"
        octets /= 1024


def afficher_rapport_rendus(commande: BaseCommand, r) -> None:
    w, style = commande.stdout.write, commande.style
    if r.dry_run:
        w(f"Rendus web à générer : {r.generees} (sur {r.photos} photos)")
        return
    w(f"Photos : {r.photos} · rendus générés {r.generees} · déjà à jour {r.inchangees}")
    if r.generees:
        w(f"Durée : {r.duree:.1f} s ({r.duree / r.generees:.2f} s par photo)")
    w(f"Cache : {r.fichiers_cache} fichiers, {_taille_lisible(r.octets_cache)}")
    if r.erreurs:
        w(style.WARNING(f"Erreurs ({len(r.erreurs)}, retentées à la prochaine relance) :"))
        for chemin, message in r.erreurs:
            w(f"  - {chemin} : {message}")
    else:
        w(style.SUCCESS("✔ Tous les rendus sont à jour"))


class Command(BaseCommand):
    help = "Génère les rendus web (WebP sans métadonnées) des photos dont l'original a changé."

    def add_arguments(self, parser):
        parser.add_argument("--voyage", help="Slug du voyage (par défaut : tous)")
        parser.add_argument("--force", action="store_true", help="Régénère tout, même les rendus à jour")
        parser.add_argument(
            "--processus", type=int, default=PROCESSUS_PAR_DEFAUT,
            help=f"Nombre de processus en parallèle (défaut : {PROCESSUS_PAR_DEFAUT})",
        )
        parser.add_argument("--dry-run", action="store_true", help="Compte les rendus à générer, sans rien faire")

    def handle(self, *args, **options):
        voyage = None
        if options["voyage"]:
            try:
                voyage = Voyage.objects.get(slug=options["voyage"])
            except Voyage.DoesNotExist:
                slugs = ", ".join(Voyage.objects.values_list("slug", flat=True)) or "aucun"
                raise CommandError(f"Voyage inconnu : « {options['voyage']} » (existants : {slugs})") from None
        if options["processus"] < 1:
            raise CommandError("--processus doit valoir au moins 1")
        try:
            rapport = generer_rendus(
                fabrique_client=creer_client,
                voyage=voyage,
                force=options["force"],
                processus=options["processus"],
                dry_run=options["dry_run"],
                progression=self._progression,
            )
        except NextcloudErreur as exc:
            raise CommandError(str(exc)) from None
        afficher_rapport_rendus(self, rapport)

    def _progression(self, i, total, chemin):
        if i == 1 or i % 25 == 0 or i == total:
            self.stdout.write(f"  {i}/{total}  {chemin.rsplit('/', 1)[-1]}")
