"""Étape 5d : compléter la date et la position des médias (surtout WhatsApp).

Analyse des noms WhatsApp, import (sources, proposition, valeurs manuelles
conservées), opérations de complétion (changement de jour, lot, « entre »,
« reprendre de la voisine »), écran de l'admin et géocodage.
"""

import json
from datetime import date, datetime, timedelta, timezone
from unittest import mock
from zoneinfo import ZoneInfo

import requests
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from voyages import completion, geocodage
from voyages.completion import CompletionErreur
from voyages.importation import importer_voyage
from voyages.models import Jour, LieuCherche, Photo, Source
from voyages.noms import analyser_whatsapp, est_whatsapp, proposer_date_whatsapp

from .donnees import creer_photo, creer_voyage
from .fabrique import image
from .test_importation import DOSSIER, FauxClient, photo_tokyo

TOKYO = ZoneInfo("Asia/Tokyo")


def tokyo(jour, heure, minute=0, seconde=0, mois=6):
    return datetime(2025, mois, jour, heure, minute, seconde, tzinfo=TOKYO)


# --- Noms WhatsApp -------------------------------------------------------------------


class NomsWhatsappTests(SimpleTestCase):
    def test_noms_reconnus(self):
        self.assertEqual(analyser_whatsapp("IMG-20250604-WA0012.jpg"), (date(2025, 6, 4), 12))
        self.assertEqual(analyser_whatsapp("Shared/Japon/Valérie/VID-20250611-WA0075.mp4"), (date(2025, 6, 11), 75))
        self.assertEqual(analyser_whatsapp("img-20250604-wa0001 (1).jpeg"), (date(2025, 6, 4), 1))

    def test_noms_refuses(self):
        for nom in [
            "IMG_20250604_123456.jpg",  # appareil photo Android, pas WhatsApp
            "IMG-20251304-WA0001.jpg",  # mois 13
            "IMG-20250230-WA0001.jpg",  # 30 février
            "IMG-19800101-WA0001.jpg",  # trop ancien
            "AUD-20250604-WA0001.opus",  # ni photo ni vidéo
            "25-06-03 08-20-53 3981.mov",
            "X-IMG-20250604-WA0001.jpg",
        ]:
            with self.subTest(nom=nom):
                self.assertIsNone(analyser_whatsapp(nom))
                self.assertFalse(est_whatsapp(nom))

    def test_heure_du_fichier_si_elle_tombe_le_jour_du_nom(self):
        recu = datetime(2025, 6, 3, 17, 20, 7, 500, tzinfo=timezone.utc)  # 4 juin 02:20:07 à Tokyo
        proposee = proposer_date_whatsapp("IMG-20250604-WA0000.jpg", recu, TOKYO)
        self.assertEqual(proposee, tokyo(4, 2, 20, 7))
        self.assertEqual(proposee.tzinfo, timezone.utc)

    def test_midi_si_le_fichier_est_d_un_autre_jour(self):
        recu = datetime(2025, 6, 12, 1, 0, tzinfo=timezone.utc)
        self.assertEqual(proposer_date_whatsapp("IMG-20250604-WA0000.jpg", recu, TOKYO), tokyo(4, 12))
        self.assertEqual(proposer_date_whatsapp("IMG-20250604-WA0000.jpg", None, TOKYO), tokyo(4, 12))

    def test_pas_de_proposition_hors_whatsapp(self):
        self.assertIsNone(proposer_date_whatsapp("IMG_0001.jpg", None, TOKYO))


# --- Import --------------------------------------------------------------------------


class ImportSourcesTests(TestCase):
    """FauxClient : fichiers modifiés le 1er juin 2025 à 12:00 UTC (21:00 à Tokyo)."""

    def setUp(self):
        self.auteur = get_user_model().objects.create_user("dd")
        self.client_nc = FauxClient({
            "IMG_0001.jpg": ("e1", photo_tokyo("09:00:00", 5)),
            "Valérie/IMG-20250601-WA0003.jpg": ("w3", image(sans_exif=True)),
            "Valérie/IMG-20250604-WA0004.jpg": ("w4", image(sans_exif=True)),
            "Valérie/scan.jpg": ("s1", image(sans_exif=True)),
        })

    def importer(self):
        return importer_voyage(self.client_nc, DOSSIER, fuseau="Asia/Tokyo", auteur=self.auteur)

    def photo(self, fin):
        return Photo.objects.get(chemin_nextcloud__endswith=fin)

    def test_sources_et_proposition_whatsapp(self):
        self.importer()
        exif = self.photo("IMG_0001.jpg")
        self.assertEqual((exif.source_date, exif.source_position, exif.date_a_confirmer), ("exif", "exif", False))
        self.assertTrue(exif.visible)

        # Nom du 1er juin, reçu le 1er juin à 21:00 (Tokyo) : jour et heure de réception.
        recue = self.photo("WA0003.jpg")
        self.assertEqual((recue.source_date, recue.date_a_confirmer, recue.visible), ("nom_fichier", True, False))
        self.assertEqual(recue.prise_le, tokyo(1, 21))
        self.assertEqual(recue.source_position, "")
        # Nom du 4 juin, fichier d'un autre jour : midi.
        self.assertEqual(self.photo("WA0004.jpg").prise_le, tokyo(4, 12))
        self.assertEqual(self.photo("WA0004.jpg").jour.date, date(2025, 6, 4))

        sans_rien = self.photo("scan.jpg")
        self.assertEqual((sans_rien.source_date, sans_rien.date_a_confirmer, sans_rien.visible), ("", False, False))

    def test_reimport_conserve_les_valeurs_manuelles(self):
        self.importer()
        recue = self.photo("WA0004.jpg")
        exif = self.photo("IMG_0001.jpg")
        completion.changer_date([recue], tokyo(5, 10))
        completion.changer_position([recue], 34.98, 135.75)
        completion.changer_position([exif], 35.5, 139.5)  # GPS corrigé à la main
        recue.refresh_from_db()
        jour, ordre = recue.jour_id, recue.ordre

        # Fichiers modifiés dans Nextcloud (etag) : tout est relu.
        for nom in ["IMG_0001.jpg", "Valérie/IMG-20250604-WA0004.jpg"]:
            etag, octets = self.client_nc.fichiers[nom]
            self.client_nc.fichiers[nom] = (etag + "-v2", octets)
        rapport = self.importer()
        self.assertEqual(rapport.mises_a_jour, 2)

        recue.refresh_from_db()
        self.assertEqual((recue.prise_le, recue.jour_id, recue.ordre), (tokyo(5, 10), jour, ordre))
        self.assertEqual((recue.latitude, recue.longitude, recue.source_position), (34.98, 135.75, "manuel"))
        self.assertEqual((recue.source_date, recue.date_a_confirmer, recue.visible), ("manuel", False, True))
        self.assertEqual(recue.etag, "w4-v2")
        exif.refresh_from_db()
        self.assertEqual((exif.latitude, exif.source_position), (35.5, "manuel"))
        self.assertEqual(exif.source_date, "exif")  # la date, elle, reste celle des EXIF

    def test_whatsapp_deja_importe_relu_une_fois_pour_la_proposition(self):
        self.importer()
        # Comme avant cette étape : date du fichier, sans source, analyse version 1.
        Photo.objects.filter(chemin_nextcloud__contains="WA").update(
            source_date="", date_a_confirmer=False, version_analyse=1
        )
        Photo.objects.exclude(chemin_nextcloud__contains="WA").update(version_analyse=1)
        self.client_nc.telechargements.clear()
        rapport = self.importer()
        self.assertEqual(rapport.reanalysees, 2)
        self.assertEqual(len(self.client_nc.telechargements), 2)  # les deux WhatsApp seulement
        self.assertTrue(self.photo("WA0004.jpg").date_a_confirmer)
        self.assertEqual(self.photo("WA0004.jpg").jour.date, date(2025, 6, 4))

        self.client_nc.telechargements.clear()
        self.assertEqual(self.importer().inchangees, 4)
        self.assertEqual(self.client_nc.telechargements, [])


# --- Opérations de complétion ---------------------------------------------------------


class CompletionTests(TestCase):
    """Voyage de 3 jours (1er au 3 juin), 4 photos par jour à 10 h, 11 h, 12 h, 13 h (Tokyo)."""

    def setUp(self):
        self.voyage = creer_voyage(jours=3, photos=4)
        self.jour1 = self.voyage.jours.get(date=date(2025, 6, 1))
        self.jour2 = self.voyage.jours.get(date=date(2025, 6, 2))
        # Un média WhatsApp masqué, rangé à la date proposée (3 juin, à confirmer).
        self.wa = creer_photo(
            self.voyage.jours.get(date=date(2025, 6, 3)), 9, heure=tokyo(3, 12), ordre=99,
            visible=False, source_date=Source.NOM_FICHIER, date_a_confirmer=True,
        )

    def ordre(self, jour):
        return list(jour.photos.order_by("ordre").values_list("pk", flat=True))

    def test_changement_de_jour_et_insertion_chronologique(self):
        avant = self.ordre(self.jour1)
        completion.changer_date([self.wa], tokyo(1, 11, 30))
        self.wa.refresh_from_db()
        self.assertEqual(self.wa.jour, self.jour1)
        self.assertEqual(self.ordre(self.jour1), [*avant[:2], self.wa.pk, *avant[2:]])
        self.assertEqual((self.wa.source_date, self.wa.date_a_confirmer, self.wa.visible), ("manuel", False, True))

    def test_nouveau_jour_cree_et_dates_du_voyage_mises_a_jour(self):
        completion.changer_date([self.wa], tokyo(5, 9))
        self.wa.refresh_from_db()
        self.assertEqual(self.wa.jour.date, date(2025, 6, 5))
        self.voyage.refresh_from_db()
        self.assertEqual(self.voyage.date_fin, date(2025, 6, 5))
        # L'ancien jour n'est jamais supprimé.
        self.assertTrue(Jour.objects.filter(voyage=self.voyage, date=date(2025, 6, 3)).exists())

    def test_nouvelle_heure_dans_le_meme_jour_replace_le_media(self):
        p1, p2, p3, p4 = self.jour1.photos.order_by("ordre")
        completion.changer_date([p1], tokyo(1, 12, 30))
        self.assertEqual(self.ordre(self.jour1), [p2.pk, p3.pk, p1.pk, p4.pk])

    def test_lot_garde_son_ordre_une_seconde_d_ecart(self):
        wa2 = creer_photo(self.wa.jour, 10, heure=tokyo(3, 12), ordre=100, visible=False)
        completion.changer_date([wa2, self.wa], tokyo(2, 10, 30))
        self.wa.refresh_from_db()
        wa2.refresh_from_db()
        # Même date d'origine : le nom départage (…-009 avant …-010).
        self.assertEqual(self.wa.prise_le, tokyo(2, 10, 30))
        self.assertEqual(wa2.prise_le, tokyo(2, 10, 30, 1))
        ordre = self.ordre(self.jour2)
        self.assertEqual(ordre.index(wa2.pk), ordre.index(self.wa.pk) + 1)
        self.assertEqual(ordre.index(self.wa.pk), 1)

    def test_placer_entre_deux_medias(self):
        p1, p2, p3, p4 = self.jour2.photos.order_by("ordre")
        wa2 = creer_photo(self.wa.jour, 10, heure=tokyo(3, 13), ordre=100, visible=False)
        completion.placer_entre([self.wa, wa2], p3, p2)  # ordre des références indifférent
        self.wa.refresh_from_db()
        wa2.refresh_from_db()
        self.assertEqual(self.ordre(self.jour2), [p1.pk, p2.pk, self.wa.pk, wa2.pk, p3.pk, p4.pk])
        self.assertEqual(self.wa.prise_le, p2.prise_le + timedelta(minutes=20))
        self.assertEqual(wa2.prise_le, p2.prise_le + timedelta(minutes=40))

    def test_placer_entre_respecte_l_ordre_choisi_meme_a_heures_egales(self):
        p1, p2, *_ = self.jour2.photos.order_by("ordre")
        Photo.objects.filter(pk=p2.pk).update(prise_le=p1.prise_le)
        p2.refresh_from_db()
        completion.placer_entre([self.wa], p1, p2)
        self.assertEqual(self.ordre(self.jour2)[:3], [p1.pk, self.wa.pk, p2.pk])

    def test_reprendre_position_et_heure_de_la_voisine(self):
        voisine = self.jour2.photos.order_by("ordre")[1]
        completion.reprendre_de([self.wa], voisine, position=True, heure=True)
        self.wa.refresh_from_db()
        self.assertEqual((self.wa.latitude, self.wa.longitude, self.wa.altitude),
                         (voisine.latitude, voisine.longitude, voisine.altitude))
        self.assertEqual(self.wa.source_position, "manuel")
        self.assertEqual(self.wa.prise_le, voisine.prise_le + timedelta(seconds=1))
        ordre = self.ordre(self.jour2)
        self.assertEqual(ordre.index(self.wa.pk), ordre.index(voisine.pk) + 1)

    def test_reprendre_la_position_seule_ne_touche_pas_la_date(self):
        voisine = self.jour2.photos.first()
        completion.reprendre_de([self.wa], voisine, position=True, heure=False)
        self.wa.refresh_from_db()
        self.assertEqual((self.wa.prise_le, self.wa.date_a_confirmer, self.wa.visible), (tokyo(3, 12), True, False))

    def test_position_appliquee_au_lot(self):
        p1, p2 = self.jour1.photos.order_by("ordre")[:2]
        completion.changer_position([p1, p2, self.wa], 34.9858, 135.7588)
        for photo in (p1, p2, self.wa):
            photo.refresh_from_db()
            self.assertEqual((photo.latitude, photo.longitude, photo.altitude), (34.9858, 135.7588, None))
            self.assertEqual(photo.source_position, "manuel")

    def test_confirmer_la_date_proposee(self):
        completion.confirmer_date([self.wa])
        self.wa.refresh_from_db()
        self.assertEqual((self.wa.prise_le, self.wa.jour.date), (tokyo(3, 12), date(2025, 6, 3)))
        self.assertEqual((self.wa.source_date, self.wa.date_a_confirmer, self.wa.visible), ("manuel", False, True))

    def test_erreurs(self):
        autre = creer_voyage("autre", jours=1, photos=1)
        etrangere = autre.jours.get().photos.get()
        sans_gps = creer_photo(self.jour1, 20, ordre=20)
        cas = [
            lambda: completion.changer_date([], tokyo(1, 9)),
            lambda: completion.changer_date([self.wa, etrangere], tokyo(1, 9)),
            lambda: completion.changer_date([self.wa], datetime(2025, 6, 1, 9)),  # sans fuseau
            lambda: completion.changer_position([self.wa], 95, 10),
            lambda: completion.reprendre_de([self.wa], sans_gps, position=True),
            lambda: completion.reprendre_de([self.wa], self.wa, position=True),
            lambda: completion.reprendre_de([self.wa], etrangere, position=True),
            lambda: completion.reprendre_de([self.wa], sans_gps, position=False, heure=False),
            lambda: completion.placer_entre([self.wa], self.wa, sans_gps),
        ]
        for i, appel in enumerate(cas):
            with self.subTest(cas=i), self.assertRaises(CompletionErreur):
                appel()

    def test_le_trace_et_le_jour_du_site_suivent(self):
        """Critère de fin : le média complété apparaît dans le bon jour et sur la carte."""
        completion.changer_position([self.wa], 34.9858, 135.7588)
        completion.changer_date([self.wa], tokyo(2, 11, 30))
        voyage = self.client.get(reverse("voyage", args=[self.voyage.slug])).json()
        self.assertIn({"lat": 34.9858, "lon": 135.7588, "jour": "2025-06-02"}, voyage["trace"])
        jour = self.client.get(reverse("jour", args=[self.voyage.slug, "2025-06-02"])).json()
        self.assertIn(self.wa.pk, [m["id"] for m in jour["photos"]])


# --- Écran de l'admin -----------------------------------------------------------------


class EcranCompletionTests(TestCase):
    def setUp(self):
        self.voyage = creer_voyage(jours=2, photos=3)
        self.wa = creer_photo(
            self.voyage.jours.get(date=date(2025, 6, 2)), 9, heure=tokyo(2, 12), ordre=99,
            visible=False, source_date=Source.NOM_FICHIER, date_a_confirmer=True,
        )
        self.admin = get_user_model().objects.create_superuser("admin", password="x")
        self.client.force_login(self.admin)
        # Jamais de vrai processus d'export XMP depuis les tests (il viserait la vraie base).
        patch = mock.patch("voyages.admin_completion.subprocess.Popen")
        self.popen = patch.start()
        self.addCleanup(patch.stop)

    def poster(self, client=None, **donnees):
        client = client or self.client
        return client.post(
            reverse("admin:voyages_completer_appliquer"),
            json.dumps({"voyage": self.voyage.pk, **donnees}), content_type="application/json",
        )

    def test_page_et_lien_depuis_la_liste(self):
        page = self.client.get(reverse("admin:voyages_photo_completer"))
        self.assertContains(page, 'id="completer"')
        self.assertContains(page, "voyages/maplibre/maplibre-gl.mjs")
        self.assertContains(page, '"a_completer": 1')
        liste = self.client.get(reverse("admin:voyages_photo_changelist"))
        self.assertContains(liste, reverse("admin:voyages_photo_completer"))

    def test_reserve_a_l_equipe(self):
        anonyme = Client()
        for nom in ["voyages_photo_completer", "voyages_completer_medias", "voyages_completer_appliquer"]:
            self.assertEqual(anonyme.get(reverse(f"admin:{nom}"), {"voyage": self.voyage.pk}).status_code, 302)
        self.assertEqual(self.poster(anonyme, ids=[self.wa.pk], action="confirmer").status_code, 302)
        # Équipe sans le droit de modifier les médias.
        lecteur = get_user_model().objects.create_user("lecteur", password="x", is_staff=True)
        client = Client()
        client.force_login(lecteur)
        self.assertEqual(client.get(reverse("admin:voyages_photo_completer")).status_code, 403)
        self.assertEqual(self.poster(client, ids=[self.wa.pk], action="confirmer").status_code, 403)
        self.wa.refresh_from_db()
        self.assertTrue(self.wa.date_a_confirmer)

    def test_csrf_exige(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(self.poster(client, ids=[self.wa.pk], action="confirmer").status_code, 403)

    def test_liste_filtree_et_comptes(self):
        Photo.objects.filter(pk=self.voyage.jours.first().photos.first().pk).update(latitude=None, longitude=None)
        donnees = self.client.get(reverse("admin:voyages_completer_medias"), {"voyage": self.voyage.pk}).json()
        self.assertEqual(donnees["comptes"], {
            "a_completer": 2, "sans_date": 0, "a_confirmer": 1, "sans_position": 2, "tout": 7,
        })
        wa = next(m for m in donnees["medias"] if m["id"] == self.wa.pk)
        self.assertEqual(wa["instant"], "2025-06-02T12:00:00+09:00")
        self.assertTrue(wa["date_a_confirmer"])
        self.assertTrue(wa["miniature"].endswith("-miniature.webp"))
        confirmer = self.client.get(
            reverse("admin:voyages_completer_medias"), {"voyage": self.voyage.pk, "filtre": "a_confirmer"}
        ).json()
        self.assertEqual([m["id"] for m in confirmer["medias"]], [self.wa.pk])

    def test_contexte_et_jour(self):
        contexte = self.client.get(reverse("admin:voyages_completer_voyage"), {"voyage": self.voyage.pk}).json()
        self.assertEqual([j["date"] for j in contexte["jours"]], ["2025-06-01", "2025-06-02"])
        self.assertEqual(len(contexte["positions"]), 6)
        jour = self.client.get(
            reverse("admin:voyages_completer_jour"), {"voyage": self.voyage.pk, "date": "2025-06-02"}
        ).json()
        self.assertEqual(len(jour["medias"]), 4)
        self.assertEqual(jour["medias"][-1]["id"], self.wa.pk)

    def test_appliquer_date_heure_locale(self):
        reponse = self.poster(ids=[self.wa.pk], action="date", instant="2025-06-01T10:30:00")
        self.assertEqual(reponse.status_code, 200)
        commande = self.popen.call_args.args[0]
        self.assertEqual(commande[-3:], ["exporter_xmp", "--photos", str(self.wa.pk)])
        self.assertEqual(reponse.json()["medias"][0]["jour"], "2025-06-01")
        self.wa.refresh_from_db()
        self.assertEqual(self.wa.prise_le, tokyo(1, 10, 30))

    def test_appliquer_entre_reprendre_position(self):
        p1, p2, _ = self.voyage.jours.get(date=date(2025, 6, 1)).photos.order_by("ordre")
        self.assertEqual(self.poster(ids=[self.wa.pk], action="entre", a=p1.pk, b=p2.pk).status_code, 200)
        self.assertEqual(self.poster(ids=[self.wa.pk], action="reprendre", reference=p2.pk, position=True).status_code, 200)
        self.wa.refresh_from_db()
        self.assertEqual((self.wa.jour.date, self.wa.latitude), (date(2025, 6, 1), p2.latitude))
        self.assertEqual(self.poster(ids=[self.wa.pk], action="position", lat="35.1", lon=139.2).status_code, 200)
        self.wa.refresh_from_db()
        self.assertEqual((self.wa.latitude, self.wa.longitude), (35.1, 139.2))

    def test_appliquer_refuse_les_requetes_invalides(self):
        autre = creer_voyage("autre", jours=1, photos=1).jours.get().photos.get()
        for donnees in [
            {"ids": [], "action": "confirmer"},
            {"ids": [autre.pk], "action": "confirmer"},  # média d'un autre voyage
            {"ids": [self.wa.pk], "action": "supprimer"},
            {"ids": [self.wa.pk], "action": "date", "instant": "demain"},
            {"ids": [self.wa.pk], "action": "position", "lat": "x", "lon": 1},
            {"ids": [self.wa.pk], "action": "reprendre", "reference": autre.pk, "position": True},
        ]:
            with self.subTest(donnees=donnees):
                reponse = self.poster(**donnees)
                self.assertEqual(reponse.status_code, 400)
                self.assertIn("erreur", reponse.json())
        self.assertEqual(self.client.get(reverse("admin:voyages_completer_appliquer")).status_code, 405)
        self.popen.assert_not_called()  # rien d'exporté quand rien n'a changé

    @override_settings(NEXTCLOUD_DOSSIER_EXPORT="")
    def test_sans_dossier_d_export_rien_n_est_lance(self):
        self.assertEqual(self.poster(ids=[self.wa.pk], action="confirmer").status_code, 200)
        self.popen.assert_not_called()

    def test_recherche_de_lieu_orientee_vers_le_voyage(self):
        with mock.patch("voyages.geocodage.chercher", return_value=[{"nom": "Kyoto", "lat": 35.0, "lon": 135.7}]) as cherche:
            reponse = self.client.get(reverse("admin:voyages_completer_lieux"), {"voyage": self.voyage.pk, "q": "Kyoto"})
        self.assertEqual(reponse.json()["resultats"][0]["nom"], "Kyoto")
        requete, autour = cherche.call_args.args
        self.assertEqual(requete, "Kyoto")
        ouest, sud, est, nord = autour
        self.assertTrue(ouest < 139.0 < est and sud < 35.0 < nord)

    def test_recherche_de_lieu_en_erreur(self):
        with mock.patch("voyages.geocodage.chercher", side_effect=geocodage.GeocodageErreur("indisponible")):
            reponse = self.client.get(reverse("admin:voyages_completer_lieux"), {"voyage": self.voyage.pk, "q": "x y"})
        self.assertEqual(reponse.status_code, 502)


# --- Géocodage ------------------------------------------------------------------------


class GeocodageTests(TestCase):
    def setUp(self):
        patch = mock.patch("voyages.geocodage.time.sleep")
        self.sommeil = patch.start()
        self.addCleanup(patch.stop)

    def reponse(self, donnees):
        reponse = mock.Mock()
        reponse.json.return_value = donnees
        reponse.raise_for_status.return_value = None
        return reponse

    def test_appel_puis_cache(self):
        bruts = [{"display_name": "Kiyomizu-dera, Kyoto", "lat": "34.9948", "lon": "135.7850"}]
        with mock.patch("voyages.geocodage.requests.get", return_value=self.reponse(bruts)) as get:
            premier = geocodage.chercher("  Kiyomizu   dera ", autour=(135.0, 34.0, 140.0, 36.0))
            second = geocodage.chercher("kiyomizu dera", autour=(135.0, 34.0, 140.0, 36.0))
        self.assertEqual(premier, [{"nom": "Kiyomizu-dera, Kyoto", "lat": 34.9948, "lon": 135.785}])
        self.assertEqual(second, premier)
        self.assertEqual(get.call_count, 1)  # la seconde vient du cache
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["q"], "Kiyomizu dera")
        self.assertEqual(params["viewbox"], "135.0,34.0,140.0,36.0")
        self.assertEqual(params["format"], "jsonv2")
        self.assertTrue(get.call_args.kwargs["headers"]["User-Agent"].startswith("CarnetDeVoyages/"))
        self.assertEqual(LieuCherche.objects.count(), 1)

    @override_settings(NOMINATIM_CONTACT="https://exemple.org/contact")
    def test_contact_dans_le_user_agent(self):
        self.assertEqual(geocodage.user_agent(), "CarnetDeVoyages/1.0 (https://exemple.org/contact)")

    def test_recherche_trop_courte_sans_appel(self):
        with mock.patch("voyages.geocodage.requests.get") as get:
            self.assertEqual(geocodage.chercher(" a "), [])
        get.assert_not_called()

    def test_une_requete_par_seconde_au_plus(self):
        with mock.patch("voyages.geocodage.requests.get", return_value=self.reponse([])):
            geocodage.chercher("Osaka")
            geocodage.chercher("Nara")
        self.assertTrue(self.sommeil.called)
        self.assertLessEqual(self.sommeil.call_args.args[0], geocodage.INTERVALLE_S)

    def test_erreur_reseau(self):
        with mock.patch("voyages.geocodage.requests.get", side_effect=requests.ConnectionError()):
            with self.assertRaises(geocodage.GeocodageErreur):
                geocodage.chercher("Tokyo")
        self.assertFalse(LieuCherche.objects.exists())
