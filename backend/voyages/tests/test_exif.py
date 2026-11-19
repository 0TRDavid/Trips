from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase
from PIL.TiffImagePlugin import IFDRational

from voyages.exif import _appareil, extraire_metadonnees

from .fabrique import image

TOKYO = ZoneInfo("Asia/Tokyo")


class ExtractionTests(SimpleTestCase):
    def verifier_photo_complete(self, format, orientation_attendue):
        contenu = image(
            format, date="2025:04:05 14:30:00", decalage="+09:00",
            lat=35.658581, lon=139.745433, altitude=42.5, orientation=6,
        )
        meta = extraire_metadonnees(contenu, TOKYO)

        self.assertEqual(meta.prise_le, datetime(2025, 4, 5, 5, 30, tzinfo=timezone.utc))
        self.assertAlmostEqual(meta.latitude, 35.658581, places=5)
        self.assertAlmostEqual(meta.longitude, 139.745433, places=5)
        self.assertAlmostEqual(meta.altitude, 42.5)
        self.assertEqual(meta.appareil, "Apple iPhone 15 Pro")
        self.assertEqual(meta.orientation, orientation_attendue)

    def test_jpeg_metadonnees_completes(self):
        self.verifier_photo_complete("JPEG", 6)

    def test_heic_metadonnees_completes(self):
        # libheif applique la rotation au décodage et pillow-heif remet l'EXIF à 1 :
        # l'image décodée est déjà droite, il ne reste aucune rotation à appliquer.
        self.verifier_photo_complete("HEIF", 1)

    def test_hemispheres_sud_ouest_et_altitude_negative(self):
        contenu = image(lat=-22.951916, lon=-43.210487, altitude=-12.0)
        meta = extraire_metadonnees(contenu, TOKYO)

        self.assertAlmostEqual(meta.latitude, -22.951916, places=5)
        self.assertAlmostEqual(meta.longitude, -43.210487, places=5)
        self.assertAlmostEqual(meta.altitude, -12.0)

    def test_decalage_explicite_prioritaire_sur_le_fuseau_du_voyage(self):
        # Photo prise à Paris (+02:00) pendant un voyage réglé sur Tokyo.
        contenu = image(date="2025:04:05 08:00:00", decalage="+02:00")
        meta = extraire_metadonnees(contenu, TOKYO)

        self.assertEqual(meta.prise_le, datetime(2025, 4, 5, 6, 0, tzinfo=timezone.utc))

    def test_sans_decalage_heure_lue_dans_le_fuseau_du_voyage(self):
        contenu = image(date="2025:04:05 08:00:00", decalage=None)
        meta = extraire_metadonnees(contenu, TOKYO)

        self.assertEqual(meta.prise_le, datetime(2025, 4, 4, 23, 0, tzinfo=timezone.utc))

    def test_horloge_de_l_appareil_pour_une_date_sans_decalage(self):
        contenu = image(date="2025:06:05 14:16:00", marque="Canon", modele="Canon EOS 100D")
        meta = extraire_metadonnees(contenu, TOKYO, {"Canon EOS 100D": timezone.utc})

        self.assertEqual(meta.prise_le, datetime(2025, 6, 5, 14, 16, tzinfo=timezone.utc))

    def test_horloge_ignoree_si_decalage_present(self):
        contenu = image(date="2025:06:05 21:20:00", decalage="+09:00")
        meta = extraire_metadonnees(contenu, TOKYO, {"Apple iPhone 15 Pro": timezone.utc})

        self.assertEqual(meta.prise_le, datetime(2025, 6, 5, 12, 20, tzinfo=timezone.utc))

    def test_image_sans_exif(self):
        for format in ("JPEG", "HEIF"):
            with self.subTest(format=format):
                meta = extraire_metadonnees(image(format, sans_exif=True), TOKYO)
                self.assertIsNone(meta.prise_le)
                self.assertIsNone(meta.latitude)
                self.assertIsNone(meta.altitude)
                self.assertEqual(meta.appareil, "")
                self.assertIsNone(meta.orientation)

    def test_fichier_qui_n_est_pas_une_image(self):
        meta = extraire_metadonnees(b"pas une image", TOKYO)
        self.assertIsNone(meta.prise_le)

    def test_date_vide_ou_illisible(self):
        meta = extraire_metadonnees(image(date="    :  :     :  :  "), TOKYO)
        self.assertIsNone(meta.prise_le)

    def test_gps_mal_forme_ignore_sans_erreur(self):
        zero = IFDRational(1, 0)
        gps = {1: "N", 2: (zero, zero, zero), 3: "E", 4: (zero, zero, zero), 5: b"\x00", 6: zero}
        meta = extraire_metadonnees(image(gps=gps), TOKYO)

        self.assertIsNone(meta.latitude)
        self.assertIsNone(meta.longitude)
        self.assertIsNone(meta.altitude)
        # Le reste est toujours lu.
        self.assertIsNotNone(meta.prise_le)


class AppareilTests(SimpleTestCase):
    def test_marque_et_modele(self):
        self.assertEqual(_appareil("Apple", "iPhone 15 Pro"), "Apple iPhone 15 Pro")

    def test_marque_deja_dans_le_modele(self):
        self.assertEqual(_appareil("Canon", "Canon EOS R6"), "Canon EOS R6")

    def test_valeurs_manquantes_ou_bourrees(self):
        self.assertEqual(_appareil(None, "Pixel 8"), "Pixel 8")
        self.assertEqual(_appareil("SONY\x00", None), "SONY")
        self.assertEqual(_appareil(None, None), "")
