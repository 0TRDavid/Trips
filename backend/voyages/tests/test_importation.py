from datetime import date, datetime, timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from voyages.importation import ImportErreur, importer_voyage
from voyages.models import Jour, Photo, Voyage
from voyages.nextcloud import FichierDistant

from .fabrique import image

DOSSIER = "Shared/Japon 2025"


class FauxClient:
    """Nextcloud en mémoire : {nom: (etag, octets)}. Compte les téléchargements."""

    def __init__(self, fichiers, autres=()):
        self.fichiers = dict(fichiers)
        self.autres = list(autres)
        self.telechargements = []
        self.limites = []

    def lister(self, dossier):
        modifie = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        elements = [
            FichierDistant(f"{dossier}/{nom}", etag, len(octets), modifie)
            for nom, (etag, octets) in self.fichiers.items()
        ]
        elements += [FichierDistant(f"{dossier}/{nom}", "x", 10, modifie) for nom in self.autres]
        return sorted(elements, key=lambda f: f.chemin)

    def telecharger(self, chemin, limite=None):
        self.telechargements.append(chemin)
        self.limites.append(limite)
        octets = self.fichiers[chemin.rsplit("/", 1)[-1]][1]
        return octets[:limite] if limite else octets


def photo_tokyo(heure, jour=5):
    return image(date=f"2025:04:{jour:02d} {heure}", decalage="+09:00", lat=35.0, lon=139.0)


class ImportTests(TestCase):
    def setUp(self):
        self.auteur = get_user_model().objects.create_user("dd")

    def importer(self, client, **kwargs):
        kwargs.setdefault("fuseau", "Asia/Tokyo")
        kwargs.setdefault("auteur", self.auteur)
        return importer_voyage(client, DOSSIER, **kwargs)

    def client_de_base(self):
        return FauxClient(
            {
                "IMG_0001.HEIC": ("e1", photo_tokyo("09:00:00", 5)),
                "IMG_0002.jpg": ("e2", photo_tokyo("18:00:00", 5)),
                "IMG_0003.HEIC": ("e3", photo_tokyo("10:00:00", 7)),
            },
            autres=["IMG_0001.MOV", "IMG_0002.AAE"],
        )

    def test_premier_import_cree_voyage_jours_photos(self):
        rapport = self.importer(self.client_de_base())

        voyage = Voyage.objects.get()
        self.assertEqual(voyage.titre, "Japon 2025")
        self.assertEqual(voyage.slug, "japon-2025")
        self.assertEqual(voyage.dossier_nextcloud, DOSSIER)
        self.assertEqual(voyage.fuseau_horaire, "Asia/Tokyo")
        self.assertEqual((voyage.date_debut, voyage.date_fin), (date(2025, 4, 5), date(2025, 4, 7)))
        self.assertEqual(list(voyage.jours.values_list("date", flat=True)), [date(2025, 4, 5), date(2025, 4, 7)])
        self.assertEqual(Photo.objects.count(), 3)
        self.assertEqual((rapport.images_nextcloud, rapport.photos_en_base, rapport.creees), (3, 3, 3))
        self.assertEqual(dict(rapport.ignores), {".mov": 1, ".aae": 1})

        photo = Photo.objects.get(chemin_nextcloud=f"{DOSSIER}/IMG_0001.HEIC")
        self.assertEqual(photo.prise_le, datetime(2025, 4, 5, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(photo.etag, "e1")
        self.assertEqual(photo.appareil, "Apple iPhone 15 Pro")
        self.assertTrue(photo.visible)

    def test_regroupement_par_date_locale_autour_de_minuit(self):
        client = FauxClient({
            "soir.jpg": ("a", photo_tokyo("23:30:00", 5)),
            "nuit.jpg": ("b", photo_tokyo("00:30:00", 6)),
            # 16:00 UTC le 5 = 01:00 à Tokyo le 6.
            "utc.jpg": ("c", image(date="2025:04:05 16:00:00", decalage="+00:00")),
        })
        self.importer(client)

        jour_de = {p.chemin_nextcloud.rsplit("/", 1)[-1]: p.jour.date for p in Photo.objects.select_related("jour")}
        self.assertEqual(jour_de, {"soir.jpg": date(2025, 4, 5), "nuit.jpg": date(2025, 4, 6), "utc.jpg": date(2025, 4, 6)})

    def test_relance_sans_doublon_ni_telechargement(self):
        client = self.client_de_base()
        self.importer(client)
        client.telechargements.clear()

        rapport = self.importer(client, fuseau=None)

        self.assertEqual(Photo.objects.count(), 3)
        self.assertEqual(Jour.objects.count(), 2)
        self.assertEqual(Voyage.objects.count(), 1)
        self.assertEqual(client.telechargements, [])
        self.assertEqual((rapport.creees, rapport.mises_a_jour, rapport.inchangees), (0, 0, 3))

    def test_etag_modifie_met_a_jour_sans_ecraser_la_saisie(self):
        client = self.client_de_base()
        self.importer(client)
        photo = Photo.objects.get(chemin_nextcloud=f"{DOSSIER}/IMG_0001.HEIC")
        photo.legende, photo.favori, photo.ordre, photo.visible = "Fushimi Inari", True, 4, False
        photo.save()

        # Le fichier a été retouché : nouvelle date (le 6) et nouvel etag.
        client.fichiers["IMG_0001.HEIC"] = ("e1-v2", photo_tokyo("08:00:00", 6))
        client.telechargements.clear()
        rapport = self.importer(client)

        photo.refresh_from_db()
        self.assertEqual(client.telechargements, [f"{DOSSIER}/IMG_0001.HEIC"])
        self.assertEqual(rapport.mises_a_jour, 1)
        self.assertEqual(photo.etag, "e1-v2")
        self.assertEqual(photo.jour.date, date(2025, 4, 6))
        self.assertEqual((photo.legende, photo.favori, photo.visible), ("Fushimi Inari", True, False))
        # Elle a changé de jour : son rang dans l'ancien jour n'a plus de sens, elle se
        # range à la fin du nouveau (seule photo du 6 ici). Voir test_ordre.py.
        self.assertEqual(photo.ordre, 1)
        self.assertEqual(Photo.objects.count(), 3)

    def test_recits_et_titres_jamais_ecrases(self):
        client = self.client_de_base()
        self.importer(client)
        voyage = Voyage.objects.get()
        voyage.titre, voyage.recit_intro = "Le Japon au printemps", "Intro"
        voyage.save()
        jour = voyage.jours.first()
        jour.titre, jour.recit, jour.lieu = "Arrivée", "# Tokyo", "Shinjuku"
        jour.save()

        self.importer(client, titre="Autre titre")

        voyage.refresh_from_db()
        jour.refresh_from_db()
        self.assertEqual((voyage.titre, voyage.recit_intro), ("Le Japon au printemps", "Intro"))
        self.assertEqual((jour.titre, jour.recit, jour.lieu), ("Arrivée", "# Tokyo", "Shinjuku"))

    def test_photo_sans_date_prend_la_date_du_fichier_et_est_masquee(self):
        client = FauxClient({"capture.jpg": ("s", image(sans_exif=True))})
        rapport = self.importer(client)

        photo = Photo.objects.get()
        self.assertFalse(photo.visible)
        self.assertEqual(photo.prise_le, datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc))
        self.assertEqual(photo.jour.date, date(2025, 6, 1))  # 21:00 à Tokyo
        self.assertEqual(rapport.sans_date, [f"{DOSSIER}/capture.jpg"])

    def test_fichier_disparu_signale_et_conserve(self):
        client = self.client_de_base()
        self.importer(client)
        del client.fichiers["IMG_0003.HEIC"]

        rapport = self.importer(client)

        self.assertEqual(rapport.disparues, [f"{DOSSIER}/IMG_0003.HEIC"])
        self.assertEqual(Photo.objects.count(), 3)
        self.assertEqual((rapport.images_nextcloud, rapport.photos_en_base), (2, 3))

    def test_dry_run_n_ecrit_ni_ne_telecharge_rien(self):
        client = self.client_de_base()
        rapport = self.importer(client, dry_run=True)

        self.assertEqual(Voyage.objects.count(), 0)
        self.assertEqual(Photo.objects.count(), 0)
        self.assertEqual(client.telechargements, [])
        self.assertEqual(rapport.creees, 3)

    def test_dry_run_sans_auteur(self):
        rapport = self.importer(self.client_de_base(), dry_run=True, auteur=None)
        self.assertEqual(rapport.creees, 3)

    def test_auteur_obligatoire_pour_creer_le_voyage(self):
        with self.assertRaisesMessage(ImportErreur, "auteur"):
            self.importer(self.client_de_base(), auteur=None)

    def test_limite(self):
        rapport = self.importer(self.client_de_base(), limite=2)

        self.assertEqual(Photo.objects.count(), 2)
        self.assertEqual(rapport.images_nextcloud, 3)

    def test_fuseau_invalide(self):
        with self.assertRaisesMessage(ImportErreur, "Fuseau horaire inconnu"):
            self.importer(self.client_de_base(), fuseau="Asie/Tokio")

    def test_fuseau_obligatoire_au_premier_import(self):
        with self.assertRaisesMessage(ImportErreur, "--fuseau"):
            self.importer(self.client_de_base(), fuseau=None)

    def test_changer_de_fuseau_refuse(self):
        self.importer(self.client_de_base())
        with self.assertRaisesMessage(ImportErreur, "Asia/Tokyo"):
            self.importer(self.client_de_base(), fuseau="Europe/Paris")

    def test_slug_unique(self):
        autre = get_user_model().objects.create_user("autre")
        Voyage.objects.create(auteur=autre, titre="x", slug="japon-2025", dossier_nextcloud="ailleurs", fuseau_horaire="UTC")

        self.importer(self.client_de_base())

        self.assertTrue(Voyage.objects.filter(slug="japon-2025-2", dossier_nextcloud=DOSSIER).exists())


class Cr2EtHorlogesTests(TestCase):
    """Les vrais CR2 ne sont pas reproductibles en test : un JPEG nommé .CR2 suffit,
    Pillow détecte le format au contenu."""

    def setUp(self):
        self.auteur = get_user_model().objects.create_user("dd")

    def importer(self, client, **kwargs):
        kwargs.setdefault("fuseau", "Asia/Tokyo")
        return importer_voyage(client, DOSSIER, auteur=self.auteur, **kwargs)

    def canon(self, heure):
        # Le Canon n'écrit pas de décalage horaire.
        return image(date=f"2025:06:05 {heure}", marque="Canon", modele="Canon EOS 100D", orientation=1)

    def test_cr2_lu_par_l_en_tete_seulement(self):
        client = FauxClient({"IMG_7704.CR2": ("c", self.canon("14:16:00"))})
        self.importer(client)

        self.assertEqual(Photo.objects.count(), 1)
        self.assertEqual(client.limites, [256 * 1024])

    def test_cr2_en_tete_insuffisant_on_telecharge_tout(self):
        # Gros bloc avant les EXIF : l'en-tête ne contient pas la date.
        client = FauxClient({"IMG_7704.CR2": ("c", self.canon("14:16:00"))})
        with mock.patch("voyages.importation.OCTETS_EN_TETE", {".cr2": 10}):
            self.importer(client)

        self.assertEqual(client.limites, [10, None])
        self.assertTrue(Photo.objects.get().visible)

    def test_horloge_appareil_appliquee_et_memorisee(self):
        client = FauxClient({
            "IMG_7704.CR2": ("c", self.canon("14:16:00")),
            "IMG_4118.JPG": ("i", image(date="2025:06:05 21:20:00", decalage="+09:00")),
        })
        self.importer(client, horloges={"Canon EOS 100D": "UTC"})

        canon = Photo.objects.get(appareil="Canon EOS 100D")
        self.assertEqual(canon.prise_le, datetime(2025, 6, 5, 14, 16, tzinfo=timezone.utc))
        self.assertEqual(canon.jour.date, date(2025, 6, 5))  # 23:16 à Tokyo
        iphone = Photo.objects.get(appareil="Apple iPhone 15 Pro")
        self.assertEqual(iphone.prise_le, datetime(2025, 6, 5, 12, 20, tzinfo=timezone.utc))
        self.assertEqual(Voyage.objects.get().horloges_appareils, {"Canon EOS 100D": "UTC"})

    def test_horloge_ajoutee_apres_coup_relit_seulement_cet_appareil(self):
        client = FauxClient({
            "IMG_7704.CR2": ("c", self.canon("14:16:00")),
            "IMG_4118.JPG": ("i", image(date="2025:06:05 21:20:00", decalage="+09:00")),
        })
        self.importer(client)  # sans horloge : lu à l'heure de Tokyo
        canon = Photo.objects.get(appareil="Canon EOS 100D")
        self.assertEqual(canon.prise_le, datetime(2025, 6, 5, 5, 16, tzinfo=timezone.utc))

        client.telechargements.clear()
        rapport = self.importer(client, fuseau=None, horloges={"Canon EOS 100D": "UTC"})

        canon.refresh_from_db()
        self.assertEqual(canon.prise_le, datetime(2025, 6, 5, 14, 16, tzinfo=timezone.utc))
        self.assertEqual(client.telechargements, [f"{DOSSIER}/IMG_7704.CR2"])
        self.assertEqual((rapport.mises_a_jour, rapport.inchangees), (1, 1))

        # Relance sans option : l'horloge mémorisée reste, rien n'est relu.
        client.telechargements.clear()
        self.importer(client, fuseau=None)
        self.assertEqual(client.telechargements, [])

    def test_horloge_memorisee_seulement_apres_relecture(self):
        client = FauxClient({"IMG_7704.CR2": ("c", self.canon("14:16:00"))})
        self.importer(client)
        client.telecharger = mock.Mock(side_effect=ConnectionError("coupure"))

        with self.assertRaises(ConnectionError):
            self.importer(client, fuseau=None, horloges={"Canon EOS 100D": "UTC"})

        self.assertEqual(Voyage.objects.get().horloges_appareils, {})

    def test_horloge_decalage_fixe(self):
        client = FauxClient({"IMG_7704.CR2": ("c", self.canon("14:16:00"))})
        self.importer(client, horloges={"Canon EOS 100D": "+01:00"})

        self.assertEqual(Photo.objects.get().prise_le, datetime(2025, 6, 5, 13, 16, tzinfo=timezone.utc))

    def test_horloge_invalide(self):
        with self.assertRaisesMessage(ImportErreur, "Fuseau horaire inconnu"):
            self.importer(FauxClient({}), horloges={"Canon EOS 100D": "Mars/Olympus"})
