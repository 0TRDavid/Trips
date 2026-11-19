from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from voyages.models import Voyage

from .fabrique import CacheTemporaire
from .test_importation import FauxClient, photo_tokyo


class CommandeTests(CacheTemporaire, TestCase):
    def setUp(self):
        super().setUp()
        get_user_model().objects.create_superuser("dd", password="x")
        self.client_nc = FauxClient(
            {"a.HEIC": ("1", photo_tokyo("09:00:00")), "b.jpg": ("2", photo_tokyo("10:00:00"))},
            autres=["a.MOV"],
        )

    def lancer(self, *args):
        sortie = StringIO()
        with mock.patch("voyages.management.commands.import_voyage.creer_client", return_value=self.client_nc):
            call_command("import_voyage", *args, stdout=sortie)
        return sortie.getvalue()

    def test_import_affiche_le_rapport(self):
        sortie = self.lancer("/Shared/Japon 2025/", "--fuseau", "Asia/Tokyo")

        self.assertIn("Images dans Nextcloud : 2", sortie)
        self.assertIn("Photos en base        : 2", sortie)
        self.assertIn(".mov : 1", sortie)
        self.assertIn("concordent", sortie)
        self.assertEqual(Voyage.objects.get().auteur.username, "dd")

    def test_erreur_d_import_devient_command_error(self):
        with self.assertRaisesMessage(CommandError, "--fuseau"):
            self.lancer("Shared/Japon 2025")

    def test_auteur_inconnu(self):
        with self.assertRaisesMessage(CommandError, "inconnu"):
            self.lancer("Shared/Japon 2025", "--fuseau", "Asia/Tokyo", "--auteur", "personne")

    def test_horloge_memorisee_et_affichee(self):
        sortie = self.lancer("Shared/Japon 2025", "--fuseau", "Asia/Tokyo", "--horloge", "Canon EOS 100D=UTC")

        self.assertIn("horloge Canon EOS 100D : UTC", sortie)
        self.assertEqual(Voyage.objects.get().horloges_appareils, {"Canon EOS 100D": "UTC"})

    def test_horloge_mal_formee(self):
        with self.assertRaisesMessage(CommandError, "APPAREIL=FUSEAU"):
            self.lancer("Shared/Japon 2025", "--fuseau", "Asia/Tokyo", "--horloge", "Canon")

    @override_settings(NEXTCLOUD_URL="", NEXTCLOUD_USER="", NEXTCLOUD_PASSWORD="")
    def test_variables_env_manquantes(self):
        with self.assertRaisesMessage(CommandError, "NEXTCLOUD_URL"):
            call_command("import_voyage", "Shared/Japon 2025", "--fuseau", "Asia/Tokyo", stdout=StringIO())
