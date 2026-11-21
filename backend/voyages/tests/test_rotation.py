"""Rotation manuelle d'un média : rendus image et vidéo, clé du cache, import, XMP, admin."""

import json
import subprocess
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image

from voyages.generation import cle_rendus, generer_rendus
from voyages.importation import importer_voyage
from voyages.models import Photo
from voyages.rendus import produire_rendus
from voyages.rendus_video import _filtre_commun, dimensions_tournees, filtre_rotation, produire_videos
from voyages.video import InfosVideo, entree_memoire
from voyages.xmp import contenu_xmp, orientation_corrigee

from .donnees import creer_photo, creer_voyage
from .fabrique import BLEU, FFMPEG, ROUGE, CacheTemporaire, photo_bicolore, video
from .test_importation import DOSSIER, FauxClient, photo_tokyo


def proche(pixel, attendu, tolerance=40):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, attendu))


class RenduImageTests(CacheTemporaire, SimpleTestCase):
    """photo_bicolore : 64×32, moitié gauche rouge, moitié droite bleue."""

    def miniature(self, rotation, orientation=None):
        resultat = produire_rendus(photo_bicolore(orientation=orientation), self.cache, "rendus/1/t", rotation)
        fichier = next(f for f in resultat.fichiers if f.taille == "miniature")
        return resultat, Image.open(self.cache / fichier.fichier).convert("RGB")

    def test_quart_de_tour_a_droite(self):
        resultat, rendu = self.miniature(90)
        self.assertEqual((resultat.largeur, resultat.hauteur), (32, 64))
        # Sens horaire : la gauche (rouge) passe en haut.
        self.assertTrue(proche(rendu.getpixel((16, 8)), ROUGE))
        self.assertTrue(proche(rendu.getpixel((16, 56)), BLEU))

    def test_quart_de_tour_a_gauche(self):
        _, rendu = self.miniature(270)
        self.assertEqual(rendu.size, (32, 64))
        self.assertTrue(proche(rendu.getpixel((16, 8)), BLEU))

    def test_demi_tour(self):
        resultat, rendu = self.miniature(180)
        self.assertEqual((resultat.largeur, resultat.hauteur), (64, 32))
        self.assertTrue(proche(rendu.getpixel((8, 16)), BLEU))
        self.assertTrue(proche(rendu.getpixel((56, 16)), ROUGE))

    def test_appliquee_apres_l_orientation_exif(self):
        # EXIF 6 (rouge en haut) puis demi-tour : rouge en bas.
        _, rendu = self.miniature(180, orientation=6)
        self.assertEqual(rendu.size, (32, 64))
        self.assertTrue(proche(rendu.getpixel((16, 56)), ROUGE))


class RenduVideoTests(SimpleTestCase):
    def test_filtres_et_dimensions(self):
        self.assertEqual(filtre_rotation(0), "")
        self.assertEqual(filtre_rotation(90), "transpose=clock")
        self.assertEqual(filtre_rotation(180), "hflip,vflip")
        self.assertEqual(filtre_rotation(270), "transpose=cclock")
        self.assertEqual(dimensions_tournees(1920, 1080, 90), (1080, 1920))
        self.assertEqual(dimensions_tournees(1920, 1080, 180), (1920, 1080))
        infos = InfosVideo(largeur=1920, hauteur=1080, duree=1.0, ips=30, hdr=False, a_son=False)
        self.assertEqual(_filtre_commun(infos), "format=yuv420p")
        self.assertTrue(_filtre_commun(infos, 180).startswith("hflip,vflip,"))


@skipUnless(FFMPEG, "ffmpeg absent")
class ProduireVideoTourneeTests(CacheTemporaire, SimpleTestCase):
    def test_quart_de_tour_echange_les_dimensions(self):
        with entree_memoire(video(duree=0.5, taille=(640, 480), son=False)) as entree:
            resultat = produire_videos(entree, self.cache, "rendus/1/t", son=False, rotation=90)
        fichier = resultat.fichiers[0]
        self.assertEqual((fichier.largeur, fichier.hauteur), (480, 640))
        sonde = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", str(self.cache / fichier.fichier)],
            capture_output=True, check=True,
        ).stdout)["streams"][0]
        self.assertEqual((sonde["width"], sonde["height"]), (480, 640))


class CacheEtImportTests(CacheTemporaire, TestCase):
    def setUp(self):
        super().setUp()
        self.auteur = get_user_model().objects.create_user("dd")
        self.client_nc = FauxClient({"IMG_0001.jpg": ("e1", photo_tokyo("09:00:00", 5))})
        self.importer()

    def importer(self):
        return importer_voyage(self.client_nc, DOSSIER, fuseau="Asia/Tokyo", auteur=self.auteur)

    def generer(self):
        return generer_rendus(fabrique_client=lambda: self.client_nc, processus=1)

    def test_sans_rotation_la_cle_reste_l_etag(self):
        photo = Photo.objects.get()
        self.assertEqual(cle_rendus(photo), "e1")

    def test_changer_la_rotation_regenere_sous_un_autre_nom(self):
        self.generer()
        photo = Photo.objects.get()
        anciens = set(photo.rendus.values_list("fichier", flat=True))
        photo.rotation = 90
        photo.save(update_fields=["rotation"])

        self.assertEqual(self.generer().generees, 1)

        photo.refresh_from_db()
        self.assertEqual(photo.rendus_etag, "e1-r90")
        nouveaux = set(photo.rendus.values_list("fichier", flat=True))
        self.assertFalse(anciens & nouveaux)  # nouvelle URL : pas d'ancienne image en cache
        self.assertEqual(self.generer().generees, 0)

    def test_l_import_n_ecrase_pas_la_rotation(self):
        Photo.objects.update(rotation=180)
        self.client_nc.fichiers["IMG_0001.jpg"] = ("e1-bis", photo_tokyo("09:00:00", 5))
        self.importer()
        self.assertEqual(Photo.objects.get().rotation, 180)


class XmpRotationTests(TestCase):
    def test_orientation_combinee(self):
        self.assertEqual(orientation_corrigee(None, 180), 3)
        self.assertEqual(orientation_corrigee(1, 90), 6)
        self.assertEqual(orientation_corrigee(6, 90), 3)
        self.assertEqual(orientation_corrigee(8, 90), 1)
        self.assertEqual(orientation_corrigee(2, 180), 4)  # miroir conservé

    def test_sidecar_avec_la_rotation_seule(self):
        voyage = creer_voyage(jours=1, photos=1)
        photo = voyage.jours.get().photos.get()
        self.assertIsNone(contenu_xmp(photo, "Asia/Tokyo"))
        photo.rotation = 180
        texte = contenu_xmp(photo, "Asia/Tokyo").decode()
        self.assertIn('tiff:Orientation="3"', texte)
        self.assertIn('carnet:Rotation="180"', texte)
        self.assertNotIn("DateTimeOriginal", texte)
        self.assertNotIn("GPS", texte)


@mock.patch("voyages.admin_completion.lancer_export_xmp")
@mock.patch("voyages.admin.lancer_regeneration")
class AdminRotationTests(TestCase):
    def setUp(self):
        voyage = creer_voyage(jours=1, photos=0)
        jour = voyage.jours.get()
        self.photo = creer_photo(jour, 1)
        self.client.force_login(get_user_model().objects.create_superuser("admin", password="x"))

    def agir(self, action):
        return self.client.post(
            reverse("admin:voyages_photo_changelist"), {"action": action, "_selected_action": [self.photo.pk]}
        )

    def test_les_actions_se_cumulent(self, regenerer, exporter):
        self.agir("tourner_1")
        self.agir("tourner_1")
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.rotation, 180)
        self.agir("tourner_3")  # 180 + 270 = 90
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.rotation, 90)
        self.agir("tourner_3")  # 90 + 270 = 0
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.rotation, 0)
        regenerer.assert_called_with([self.photo.pk])
        exporter.assert_called_with([self.photo.pk])

    def test_fiche_regenere_seulement_si_la_rotation_change(self, regenerer, exporter):
        url = reverse("admin:voyages_photo_change", args=[self.photo.pk])
        donnees = {"legende": "x", "visible": "on"}  # seuls champs modifiables, avec favori et rotation
        self.assertEqual(self.client.post(url, {**donnees, "rotation": 0}).status_code, 302)
        regenerer.assert_not_called()
        self.assertEqual(self.client.post(url, {**donnees, "rotation": 270}).status_code, 302)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.rotation, 270)
        regenerer.assert_called_once_with([self.photo.pk])
