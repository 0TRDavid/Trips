"""Rendus web : aucune métadonnée, orientation, sRGB, relance sans régénération."""

import base64
import io
import shutil
import subprocess
from io import StringIO
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase

from voyages.generation import generer_rendus
from voyages.importation import importer_voyage
from voyages.models import Photo, Rendu, Voyage
from voyages.rendus import produire_rendus
from voyages.thumbhash import couleur_moyenne, ratio_approximatif, thumbhash_rgb
from PIL import Image

from .fabrique import BLEU, ROUGE, CacheTemporaire, photo_bicolore, profil_display_p3
from .test_importation import DOSSIER, FauxClient, photo_tokyo

EXIFTOOL = shutil.which("exiftool")


def proche(pixel, attendu, tolerance=40):
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, attendu))


class ProduireRendusTests(CacheTemporaire, SimpleTestCase):
    def produire(self, octets):
        return produire_rendus(octets, self.cache, "rendus/1/test")

    def ouvrir(self, fichier):
        return Image.open(self.cache / fichier.fichier)

    def test_aucune_metadonnee_dans_les_rendus(self):
        source = photo_bicolore(taille=(3000, 2000), orientation=1, gps=True, xmp=True, icc=profil_display_p3())
        # La source contient bien tout ce qu'on veut voir disparaître.
        with Image.open(io.BytesIO(source)) as image:
            self.assertTrue(image.getexif().get_ifd(0x8825))
            self.assertIn("xmp", image.info)
            self.assertIn("icc_profile", image.info)

        resultat = self.produire(source)

        self.assertEqual(len(resultat.fichiers), 3)
        for fichier in resultat.fichiers:
            with self.subTest(fichier.taille):
                with self.ouvrir(fichier) as rendu:
                    self.assertEqual(rendu.format, "WEBP")
                    self.assertEqual(len(rendu.getexif()), 0)
                    self.assertFalse({"exif", "xmp", "icc_profile"} & set(rendu.info))
                octets = (self.cache / fichier.fichier).read_bytes()
                # Les métadonnées d'un WebP vivent dans des blocs dédiés : aucun ne doit exister.
                for bloc in (b"EXIF", b"XMP ", b"ICCP"):
                    self.assertNotIn(bloc, octets)
                self.assertEqual(fichier.octets, len(octets))

    @skipUnless(EXIFTOOL, "exiftool absent")
    def test_exiftool_ne_trouve_ni_gps_ni_exif(self):
        resultat = self.produire(photo_bicolore(taille=(800, 600), gps=True, xmp=True))
        chemins = [str(self.cache / f.fichier) for f in resultat.fichiers]
        sortie = subprocess.run(
            [EXIFTOOL, "-a", "-s", "-gps:all", "-exif:all", "-xmp:all", "-icc_profile:all", *chemins],
            capture_output=True, text=True, check=False,
        ).stdout
        # Seules restent les lignes de séparation « ======== fichier » et le total.
        lignes = [l for l in sortie.splitlines() if l.strip() and not l.startswith("========") and "image files read" not in l]
        self.assertEqual(lignes, [])

    def test_trois_tailles_cote_le_plus_long(self):
        resultat = self.produire(photo_bicolore(taille=(3000, 2000)))

        dimensions = {f.taille: (f.largeur, f.hauteur) for f in resultat.fichiers}
        self.assertEqual(dimensions, {"grande": (2560, 1707), "moyenne": (1280, 853), "miniature": (400, 267)})
        for fichier in resultat.fichiers:
            with self.ouvrir(fichier) as rendu:
                self.assertEqual(rendu.size, (fichier.largeur, fichier.hauteur))
        self.assertEqual((resultat.largeur, resultat.hauteur), (3000, 2000))

    def test_petite_image_jamais_agrandie(self):
        resultat = self.produire(photo_bicolore(taille=(300, 200)))

        self.assertEqual({(f.largeur, f.hauteur) for f in resultat.fichiers}, {(300, 200)})

    def verifier_portrait_rouge_en_haut(self, resultat):
        # Orientation 6 = rotation de 90° horaire : la moitié gauche (rouge) passe en haut.
        self.assertEqual((resultat.largeur, resultat.hauteur), (32, 64))
        miniature = next(f for f in resultat.fichiers if f.taille == "miniature")
        with self.ouvrir(miniature) as rendu:
            rendu = rendu.convert("RGB")
            self.assertEqual(rendu.size, (32, 64))
            self.assertTrue(proche(rendu.getpixel((16, 8)), ROUGE), rendu.getpixel((16, 8)))
            self.assertTrue(proche(rendu.getpixel((16, 56)), BLEU), rendu.getpixel((16, 56)))

    def test_orientation_heic_tourne(self):
        self.verifier_portrait_rouge_en_haut(self.produire(photo_bicolore("HEIF", orientation=6)))

    def test_orientation_jpeg_tourne(self):
        self.verifier_portrait_rouge_en_haut(self.produire(photo_bicolore("JPEG", orientation=6)))

    def test_conversion_display_p3_vers_srgb(self):
        orange = (200, 100, 50)
        source = photo_bicolore(taille=(64, 64), icc=profil_display_p3(), couleurs=(orange, orange))

        resultat = self.produire(source)

        with self.ouvrir(resultat.fichiers[0]) as rendu:
            pixel = rendu.convert("RGB").getpixel((32, 32))
        # Le rouge P3 est plus saturé que celui du sRGB : converti, il « monte ».
        self.assertGreater(pixel[0], orange[0] + 8, pixel)
        self.assertLess(pixel[2], orange[2] - 10, pixel)

    def test_couleur_dominante_et_placeholder(self):
        vert = (30, 160, 60)
        # Trois quarts verts, un quart rouge : la dominante est le vert.
        source = photo_bicolore(taille=(400, 200), couleurs=(ROUGE, vert))
        with Image.open(io.BytesIO(source)) as image:
            image = image.convert("RGB")
            image.paste(vert, (100, 0, 200, 200))
            tampon = io.BytesIO()
            image.save(tampon, "PNG")

        resultat = self.produire(tampon.getvalue())

        couleur = tuple(int(resultat.couleur[i:i + 2], 16) for i in (1, 3, 5))
        self.assertTrue(proche(couleur, vert, 25), resultat.couleur)
        hash_ = base64.b64decode(resultat.placeholder)
        self.assertLessEqual(len(hash_), 30)
        self.assertAlmostEqual(ratio_approximatif(hash_), 2.0, delta=0.4)


class ThumbHashTests(SimpleTestCase):
    def test_identique_a_l_implementation_de_reference(self):
        # Valeurs calculées avec le paquet npm « thumbhash » 0.1.1 (rgbaToThumbHash),
        # sur le même dégradé : le front décodera exactement ce que le back encode.
        def degrade(w, h):
            return bytes(
                v for y in range(h) for x in range(w)
                for v in ((x * 255) // (w - 1), (y * 255) // (h - 1), ((x + y) * 97) % 256)
            )

        attendus = {
            (80, 60): "3/cJNZqAh3eAeHeHd3h3d3BwCPh3",
            (30, 100): "4AcKOhqAcId3d3d3cIAH+Hc=",
            (100, 100): "3wcKNxqAh3dwiIeIeHd4h3eHBwd4gH8H",
        }
        for (w, h), attendu in attendus.items():
            with self.subTest(taille=(w, h)):
                self.assertEqual(base64.b64encode(thumbhash_rgb(w, h, degrade(w, h))).decode(), attendu)

    def test_couleur_moyenne_d_une_image_unie(self):
        hash_ = thumbhash_rgb(10, 10, bytes((255, 0, 0)) * 100)
        r, g, b = couleur_moyenne(hash_)
        self.assertGreater(r, 0.9)
        self.assertLess(max(g, b), 0.1)


class GenerationTests(CacheTemporaire, TestCase):
    def setUp(self):
        super().setUp()
        self.auteur = get_user_model().objects.create_user("dd")
        self.client_nc = FauxClient({
            "IMG_0001.HEIC": ("e1", photo_tokyo("09:00:00", 5)),
            "IMG_0002.jpg": ("e2", photo_tokyo("18:00:00", 5)),
            "IMG_0003.jpg": ("e3", photo_tokyo("10:00:00", 7)),
        })
        self.importer()

    def importer(self):
        return importer_voyage(self.client_nc, DOSSIER, fuseau="Asia/Tokyo", auteur=self.auteur)

    def generer(self, **kwargs):
        kwargs.setdefault("processus", 1)
        self.client_nc.telechargements.clear()
        return generer_rendus(fabrique_client=lambda: self.client_nc, **kwargs)

    def fichiers_du_cache(self):
        return sorted(p.relative_to(self.cache).as_posix() for p in self.cache.rglob("*.webp"))

    def test_generation_initiale(self):
        rapport = self.generer()

        self.assertEqual((rapport.photos, rapport.generees, rapport.inchangees), (3, 3, 0))
        self.assertEqual(Rendu.objects.count(), 9)
        self.assertEqual(len(self.fichiers_du_cache()), 9)
        self.assertEqual(rapport.fichiers_cache, 9)
        self.assertEqual(rapport.octets_cache, sum(Rendu.objects.values_list("octets", flat=True)))
        for photo in Photo.objects.all():
            self.assertEqual(photo.rendus_etag, photo.etag)
            self.assertRegex(photo.couleur, r"^#[0-9a-f]{6}$")
            self.assertTrue(photo.placeholder)
            self.assertEqual((photo.largeur, photo.hauteur), (16, 16))
        self.assertFalse(list(self.cache.rglob("*.tmp")))

    def test_relance_sans_changement_ne_regenere_rien(self):
        self.generer()
        dates = {p: (self.cache / p).stat().st_mtime_ns for p in self.fichiers_du_cache()}

        rapport = self.generer()

        self.assertEqual((rapport.generees, rapport.inchangees), (0, 3))
        self.assertEqual(self.client_nc.telechargements, [])
        self.assertEqual({p: (self.cache / p).stat().st_mtime_ns for p in self.fichiers_du_cache()}, dates)

    def test_etag_modifie_regenere_seulement_cette_photo(self):
        self.generer()
        photo = Photo.objects.get(chemin_nextcloud__endswith="IMG_0002.jpg")
        anciens = set(photo.rendus.values_list("fichier", flat=True))
        self.client_nc.fichiers["IMG_0002.jpg"] = ("e2-bis", photo_tokyo("18:00:00", 5))
        self.importer()

        rapport = self.generer()

        self.assertEqual(rapport.generees, 1)
        self.assertEqual(self.client_nc.telechargements, [photo.chemin_nextcloud])
        nouveaux = set(photo.rendus.values_list("fichier", flat=True))
        self.assertFalse(anciens & nouveaux)
        self.assertFalse(anciens & set(self.fichiers_du_cache()))  # anciens fichiers supprimés
        self.assertEqual(len(self.fichiers_du_cache()), 9)
        photo.refresh_from_db()
        self.assertEqual(photo.rendus_etag, "e2-bis")

    def test_force_regenere_tout(self):
        self.generer()
        self.assertEqual(self.generer(force=True).generees, 3)
        self.assertEqual(Rendu.objects.count(), 9)

    def test_fichier_disparu_du_cache_est_regenere(self):
        self.generer()
        (self.cache / Rendu.objects.first().fichier).unlink()

        self.assertEqual(self.generer().generees, 1)
        self.assertEqual(len(self.fichiers_du_cache()), 9)

    def test_photo_illisible_signalee_sans_bloquer_les_autres(self):
        self.client_nc.fichiers["abime.jpg"] = ("e9", b"pas une image")
        self.importer()

        rapport = self.generer()

        self.assertEqual(rapport.generees, 3)
        self.assertEqual([chemin.rsplit("/", 1)[-1] for chemin, _ in rapport.erreurs], ["abime.jpg"])
        self.assertEqual(Photo.objects.get(chemin_nextcloud__endswith="abime.jpg").rendus_etag, "")
        # Retentée à la relance.
        self.assertEqual(len(self.generer().erreurs), 1)

    def test_filtre_par_voyage(self):
        autre = Voyage.objects.create(
            auteur=self.auteur, titre="Autre", slug="autre", dossier_nextcloud="x", fuseau_horaire="UTC"
        )
        self.assertEqual(self.generer(voyage=autre).photos, 0)
        self.assertEqual(self.generer(voyage=Voyage.objects.get(slug="japon-2025")).generees, 3)

    def test_dry_run_ne_fait_rien(self):
        rapport = self.generer(dry_run=True)

        self.assertEqual(rapport.generees, 3)
        self.assertEqual(Rendu.objects.count(), 0)
        self.assertEqual(self.client_nc.telechargements, [])

    def test_en_parallele(self):
        rapport = self.generer(processus=2)

        self.assertEqual(rapport.generees, 3)
        self.assertEqual(Rendu.objects.count(), 9)
        self.assertEqual(len(self.fichiers_du_cache()), 9)


class CommandesTests(CacheTemporaire, TestCase):
    def setUp(self):
        super().setUp()
        get_user_model().objects.create_superuser("dd", password="x")
        self.client_nc = FauxClient({
            "a.jpg": ("1", photo_tokyo("09:00:00")),
            "b.HEIC": ("2", photo_tokyo("10:00:00")),
        })

    def importer(self, *options):
        sortie = StringIO()
        with mock.patch("voyages.management.commands.import_voyage.creer_client", return_value=self.client_nc):
            call_command("import_voyage", DOSSIER, "--fuseau", "Asia/Tokyo", *options, stdout=sortie)
        return sortie.getvalue()

    def generer(self, *options):
        sortie = StringIO()
        with mock.patch("voyages.management.commands.generer_rendus.creer_client", return_value=self.client_nc):
            call_command("generer_rendus", "--processus", "1", *options, stdout=sortie)
        return sortie.getvalue()

    def test_import_genere_les_rendus(self):
        sortie = self.importer()

        self.assertIn("Rendus web", sortie)
        self.assertIn("rendus générés 2", sortie)
        self.assertEqual(Rendu.objects.count(), 6)

    def test_import_sans_rendus(self):
        sortie = self.importer("--sans-rendus")

        self.assertNotIn("Rendus web", sortie)
        self.assertEqual(Rendu.objects.count(), 0)

    def test_import_dry_run_annonce_les_rendus(self):
        self.assertIn("Rendus web à générer : 2", self.importer("--dry-run"))

    def test_generer_rendus_puis_relance(self):
        self.importer("--sans-rendus")

        self.assertIn("rendus générés 2", self.generer("--voyage", "japon-2025"))
        sortie = self.generer()
        self.assertIn("rendus générés 0 · déjà à jour 2", sortie)
        self.assertIn("Cache : 6 fichiers", sortie)
        self.assertIn("rendus générés 2", self.generer("--force"))

    def test_voyage_inconnu(self):
        with self.assertRaisesMessage(CommandError, "Voyage inconnu"):
            self.generer("--voyage", "nulle-part")


class ApiPhotosTests(CacheTemporaire, TestCase):
    def setUp(self):
        super().setUp()
        auteur = get_user_model().objects.create_user("dd")
        self.client_nc = FauxClient({
            "a.jpg": ("1", photo_tokyo("09:00:00")),
            "b.jpg": ("2", photo_tokyo("10:00:00")),
        })
        importer_voyage(self.client_nc, DOSSIER, fuseau="Asia/Tokyo", auteur=auteur)
        generer_rendus(fabrique_client=lambda: self.client_nc, processus=1)

    def test_photos_avec_rendus_dimensions_couleur_placeholder(self):
        reponse = self.client.get("/api/voyages/japon-2025/photos/")

        self.assertEqual(reponse.status_code, 200)
        photos = reponse.json()
        self.assertEqual(len(photos), 2)
        photo = photos[0]
        self.assertEqual(photo["jour"], "2025-04-05")
        self.assertEqual((photo["largeur"], photo["hauteur"]), (16, 16))
        self.assertRegex(photo["couleur"], r"^#[0-9a-f]{6}$")
        self.assertTrue(photo["placeholder"])
        self.assertEqual(set(photo["rendus"]), {"miniature", "moyenne", "grande"})
        miniature = photo["rendus"]["miniature"]
        self.assertRegex(miniature["url"], r"^/media/rendus/\d+/[0-9a-f]{10}-miniature\.webp$")
        self.assertEqual((miniature["largeur"], miniature["hauteur"]), (16, 16))

    def test_aucune_coordonnee_gps_exposee(self):
        contenu = self.client.get("/api/voyages/japon-2025/photos/").content.decode()

        for cle in ("latitude", "longitude", "altitude", "chemin_nextcloud"):
            self.assertNotIn(cle, contenu)

    def test_photos_masquees_exclues(self):
        Photo.objects.filter(chemin_nextcloud__endswith="b.jpg").update(visible=False)

        self.assertEqual(len(self.client.get("/api/voyages/japon-2025/photos/").json()), 1)

    def test_voyage_inconnu(self):
        self.assertEqual(self.client.get("/api/voyages/nulle-part/photos/").status_code, 404)
