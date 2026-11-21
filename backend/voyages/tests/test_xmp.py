"""Sidecars XMP des saisies manuelles, écrits sous le dossier d'export Nextcloud seulement."""

import json
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from unittest import mock, skipUnless
from zoneinfo import ZoneInfo

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings

from voyages import completion
from voyages.export_xmp import ExportErreur, exporter, photos_avec_saisie, verifier_dossier_export
from voyages.models import Photo, Source
from voyages.nextcloud import ClientWebDAV, NextcloudErreur
from voyages.xmp import chemin_xmp, contenu_xmp

from .donnees import creer_photo, creer_voyage

EXPORT = "Shared/Métadonnées"
TOKYO = ZoneInfo("Asia/Tokyo")


class FauxClientEcriture:
    """Enregistre les écritures ; vérifie le chemin comme le vrai client."""

    def __init__(self, echecs=()):
        self.vrai = ClientWebDAV("https://nc.test", "carnet", "x", dossier_ecriture=EXPORT)
        self.fichiers, self.dossiers, self.echecs = {}, [], set(echecs)

    def creer_dossiers(self, dossier):
        self.vrai.verifier_ecriture(dossier)
        self.dossiers.append(dossier)

    def ecrire(self, chemin, octets, type_contenu):
        self.vrai.verifier_ecriture(chemin)
        if chemin in self.echecs:
            raise NextcloudErreur("Nextcloud a répondu 507")
        self.fichiers[chemin] = octets


class GardeFouEcritureTests(SimpleTestCase):
    def setUp(self):
        self.client_nc = ClientWebDAV("https://nc.test", "carnet", "x", dossier_ecriture="/Shared/Métadonnées/")

    def test_seul_le_dossier_d_export_est_accessible(self):
        self.assertEqual(self.client_nc.verifier_ecriture("/Shared/Métadonnées/a/b.xmp"), "Shared/Métadonnées/a/b.xmp")
        for chemin in [
            "Shared/Japon 2025/Hugo/IMG_1.CR2",  # un original
            "Shared/Métadonnées",  # le dossier lui-même
            "Shared/Métadonnées-bis/a.xmp",  # préfixe trompeur
            "Shared/Métadonnées/../Japon 2025/IMG_1.CR2",
            "Shared/Métadonnées/./a.xmp",
            "Shared/Métadonnées//a.xmp",
        ]:
            with self.subTest(chemin=chemin), self.assertRaises(NextcloudErreur):
                self.client_nc.verifier_ecriture(chemin)

    def test_aucune_requete_hors_du_dossier(self):
        with mock.patch.object(self.client_nc.session, "request") as requete:
            with self.assertRaises(NextcloudErreur):
                self.client_nc.ecrire("Shared/Japon 2025/IMG_1.jpg", b"x")
            with self.assertRaises(NextcloudErreur):
                self.client_nc.creer_dossiers("Shared/Japon 2025/xmp")
        requete.assert_not_called()

    def test_sans_dossier_d_export_aucune_ecriture(self):
        client = ClientWebDAV("https://nc.test", "carnet", "x")
        with self.assertRaises(NextcloudErreur):
            client.verifier_ecriture("Shared/Métadonnées/a.xmp")

    def test_put_et_mkcol(self):
        # « Japon 2025 » existe déjà (405), « xmp » est créé (201).
        reponses = [mock.Mock(status_code=405), mock.Mock(status_code=201)]
        with mock.patch.object(self.client_nc.session, "request", side_effect=reponses) as requete:
            self.client_nc.creer_dossiers("Shared/Métadonnées/Japon 2025/xmp")
        racine = "https://nc.test/remote.php/dav/files/carnet/Shared/M%C3%A9tadonn%C3%A9es"
        self.assertEqual([(c.args[0], c.args[1]) for c in requete.call_args_list], [
            ("MKCOL", f"{racine}/Japon%202025/"),
            ("MKCOL", f"{racine}/Japon%202025/xmp/"),
        ])
        with mock.patch.object(self.client_nc.session, "request", return_value=mock.Mock(status_code=201)) as requete:
            self.client_nc.ecrire("Shared/Métadonnées/a.xmp", b"<x/>", "application/rdf+xml")
        self.assertEqual(requete.call_args.args[0], "PUT")
        self.assertEqual(requete.call_args.kwargs["data"], b"<x/>")

    def test_mkcol_en_erreur(self):
        with mock.patch.object(self.client_nc.session, "request", return_value=mock.Mock(status_code=403)):
            with self.assertRaises(NextcloudErreur):
                self.client_nc.creer_dossiers("Shared/Métadonnées/x")


class ContenuXmpTests(TestCase):
    def setUp(self):
        self.voyage = creer_voyage(jours=1, photos=1)
        self.jour = self.voyage.jours.get()
        self.photo = creer_photo(self.jour, 5, heure=datetime(2025, 6, 1, 10, 38, 5, tzinfo=TOKYO), ordre=5)
        self.photo.chemin_nextcloud = "/Shared/japon-2025/Whatsapp/IMG-20250601-WA0001.jpg"
        self.photo.save(update_fields=["chemin_nextcloud"])

    def test_rien_sans_saisie_manuelle(self):
        self.assertIsNone(contenu_xmp(self.photo, "Asia/Tokyo"))
        self.assertFalse(photos_avec_saisie().exists())

    def test_seules_les_valeurs_manuelles(self):
        completion.changer_position([self.photo], 34.9671, 135.7727)
        self.photo.refresh_from_db()
        texte = contenu_xmp(self.photo, "Asia/Tokyo").decode()
        self.assertIn('exif:GPSLatitude="34,58.026000N"', texte)
        self.assertIn('exif:GPSLongitude="135,46.362000E"', texte)
        self.assertIn('carnet:SourcePosition="manuel"', texte)
        self.assertNotIn("DateTimeOriginal", texte)  # la date vient encore des EXIF

    def test_chemin_en_miroir_du_voyage(self):
        self.assertEqual(
            chemin_xmp(self.photo, "/Shared/japon-2025", EXPORT),
            "Shared/Métadonnées/japon-2025/xmp/Whatsapp/IMG-20250601-WA0001.jpg.xmp",
        )

    @skipUnless(shutil.which("exiftool"), "exiftool absent")
    def test_relu_par_exiftool(self):
        completion.changer_date([self.photo], datetime(2025, 6, 1, 10, 38, 5, tzinfo=TOKYO))
        completion.changer_position([self.photo], -33.8568, -151.2153)  # sud et ouest
        Photo.objects.filter(pk=self.photo.pk).update(altitude=-4.5)
        self.photo.refresh_from_db()
        # Un sidecar de test dans un dossier temporaire (ce n'est pas un original).
        with tempfile.TemporaryDirectory() as dossier:
            fichier = Path(dossier) / "a.xmp"
            fichier.write_bytes(contenu_xmp(self.photo, "Asia/Tokyo"))
            sortie = subprocess.run(["exiftool", "-j", "-n", "-a", "-G1", str(fichier)],
                                    capture_output=True, check=True, text=True)
        lu = json.loads(sortie.stdout)[0]
        self.assertEqual(lu["XMP-exif:DateTimeOriginal"], "2025:06:01 10:38:05+09:00")
        self.assertEqual(lu["XMP-photoshop:DateCreated"], "2025:06:01 10:38:05+09:00")
        self.assertAlmostEqual(lu["XMP-exif:GPSLatitude"], -33.8568, places=5)
        self.assertAlmostEqual(lu["XMP-exif:GPSLongitude"], -151.2153, places=5)
        # En numérique (-n), exiftool donne la valeur et le sens séparément (1 = sous le niveau de la mer).
        self.assertEqual((lu["XMP-exif:GPSAltitude"], lu["XMP-exif:GPSAltitudeRef"]), (4.5, 1))


class ExportTests(TestCase):
    def setUp(self):
        self.voyage = creer_voyage(jours=2, photos=2)
        self.p1, self.p2, self.p3, _ = Photo.objects.order_by("jour__date", "ordre")
        completion.changer_position([self.p1, self.p2], 35.0, 135.0)
        completion.changer_date([self.p3], datetime(2025, 6, 1, 15, 0, tzinfo=TOKYO))

    def test_ecrit_puis_ne_reecrit_que_ce_qui_change(self):
        client = FauxClientEcriture()
        rapport = exporter(client, photos_avec_saisie(), EXPORT)
        self.assertEqual(len(rapport.ecrits), 3)
        self.assertEqual(set(client.dossiers), {"Shared/Métadonnées/japon-2025/xmp"})
        for chemin in client.fichiers:
            self.assertTrue(chemin.startswith("Shared/Métadonnées/japon-2025/xmp/") and chemin.endswith(".jpg.xmp"))

        client = FauxClientEcriture()
        self.assertEqual((exporter(client, photos_avec_saisie(), EXPORT).a_jour, client.fichiers), (3, {}))

        completion.changer_position([self.p1], 36.0, 136.0)
        rapport = exporter(client, photos_avec_saisie(), EXPORT)
        self.assertEqual((len(rapport.ecrits), rapport.a_jour), (1, 2))

    def test_media_deplace_dans_nextcloud_reecrit_a_son_nouveau_chemin(self):
        exporter(FauxClientEcriture(), photos_avec_saisie(), EXPORT)
        Photo.objects.filter(pk=self.p1.pk).update(chemin_nextcloud="/Shared/japon-2025/Hugo/x.jpg")
        client = FauxClientEcriture()
        exporter(client, photos_avec_saisie(), EXPORT)
        self.assertEqual(list(client.fichiers), ["Shared/Métadonnées/japon-2025/xmp/Hugo/x.jpg.xmp"])

    def test_echec_signale_et_retente(self):
        chemin = chemin_xmp(self.p1, self.voyage.dossier_nextcloud, EXPORT)
        rapport = exporter(FauxClientEcriture(echecs={chemin}), photos_avec_saisie(), EXPORT)
        self.assertEqual([c for c, _ in rapport.erreurs], [chemin])
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.xmp_empreinte, "")
        client = FauxClientEcriture()
        exporter(client, photos_avec_saisie(), EXPORT)
        self.assertEqual(list(client.fichiers), [chemin])

    def test_dry_run_n_ecrit_rien(self):
        rapport = exporter(None, photos_avec_saisie(), EXPORT, dry_run=True)
        self.assertEqual(len(rapport.ecrits), 3)
        self.assertFalse(Photo.objects.exclude(xmp_empreinte="").exists())

    def test_dossier_d_export_qui_recouvre_un_voyage_refuse(self):
        for dossier in ["", "Shared/japon-2025", "Shared/japon-2025/xmp", "Shared"]:
            with self.subTest(dossier=dossier), self.assertRaises(ExportErreur):
                verifier_dossier_export(dossier)
        verifier_dossier_export(EXPORT)

    @override_settings(NEXTCLOUD_DOSSIER_EXPORT=EXPORT)
    def test_commande(self):
        client = FauxClientEcriture()
        sortie = StringIO()
        with mock.patch("voyages.management.commands.exporter_xmp.creer_client", return_value=client):
            call_command("exporter_xmp", "--photos", f"{self.p1.pk},{self.p3.pk}", stdout=sortie)
        self.assertIn("Sidecars XMP écrits : 2", sortie.getvalue())
        self.assertEqual(len(client.fichiers), 2)
        with self.assertRaises(CommandError):
            call_command("exporter_xmp", "--voyage", "inconnu", stdout=StringIO())

    @override_settings(NEXTCLOUD_DOSSIER_EXPORT="")
    def test_commande_sans_dossier_d_export(self):
        with mock.patch("voyages.management.commands.exporter_xmp.creer_client"):
            with self.assertRaises(CommandError):
                call_command("exporter_xmp", stdout=StringIO())
