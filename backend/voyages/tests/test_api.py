"""API en lecture seule : endpoints, ordre des photos, photos masquées, requêtes."""

from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from voyages.models import Jour, Photo

from .donnees import creer_photo, creer_voyage

CHAMPS_INTERDITS = ("chemin_nextcloud", "etag", "altitude", "latitude", "longitude", "appareil")


class ListeVoyagesTests(TestCase):
    def test_liste_avec_comptes_et_couverture(self):
        voyage = creer_voyage(jours=3, photos=4)
        Photo.objects.filter(jour__voyage=voyage, ordre=4).update(visible=False)  # 3 masquées

        reponse = self.client.get("/api/voyages/")

        self.assertEqual(reponse.status_code, 200)
        [v] = reponse.json()
        self.assertEqual(v["slug"], "japon-2025")
        self.assertEqual((v["date_debut"], v["date_fin"]), ("2025-06-01", "2025-06-03"))
        self.assertEqual((v["nb_jours"], v["nb_photos"]), (3, 9))
        self.assertEqual(set(v["couverture"]), {"id", "largeur", "hauteur", "couleur", "placeholder", "rendus"})
        self.assertEqual(set(v["couverture"]["rendus"]), {"miniature", "moyenne", "grande"})

    def test_couverture_choisie(self):
        voyage = creer_voyage()
        choisie = Photo.objects.filter(jour__voyage=voyage).last()
        voyage.couverture = choisie
        voyage.save()

        self.assertEqual(self.client.get("/api/voyages/").json()[0]["couverture"]["id"], choisie.id)

    def test_couverture_de_repli_premier_favori_puis_premiere_photo_visible(self):
        voyage = creer_voyage()
        photos = list(Photo.objects.filter(jour__voyage=voyage).order_by("jour__date", "ordre"))
        couverture = lambda: self.client.get("/api/voyages/").json()[0]["couverture"]["id"]  # noqa: E731

        self.assertEqual(couverture(), photos[0].id)
        Photo.objects.filter(pk=photos[0].pk).update(visible=False)
        self.assertEqual(couverture(), photos[1].id)
        Photo.objects.filter(pk=photos[6].pk).update(favori=True)
        self.assertEqual(couverture(), photos[6].id)
        Photo.objects.filter(pk=photos[6].pk).update(visible=False)  # un favori masqué ne compte pas
        self.assertEqual(couverture(), photos[1].id)

    def test_voyage_sans_photo(self):
        creer_voyage(photos=0)

        v = self.client.get("/api/voyages/").json()[0]

        self.assertEqual((v["nb_jours"], v["nb_photos"], v["couverture"]), (3, 0, None))

    def test_plus_recent_en_premier(self):
        creer_voyage("ancien", debut=date(2020, 1, 1))
        creer_voyage("recent", debut=date(2025, 1, 1))

        self.assertEqual([v["slug"] for v in self.client.get("/api/voyages/").json()], ["recent", "ancien"])


class DetailVoyageTests(TestCase):
    def setUp(self):
        self.voyage = creer_voyage(jours=3, photos=4)

    def test_detail_jours_et_recit(self):
        self.voyage.recit_intro = "Un **grand** voyage."
        self.voyage.save()
        Jour.objects.filter(voyage=self.voyage, date=date(2025, 6, 2)).update(recit="Écrit.", lieu="Kyoto")

        d = self.client.get("/api/voyages/japon-2025/").json()

        self.assertEqual(d["recit_intro"], "Un **grand** voyage.")
        self.assertEqual(d["recit_intro_html"], "<p>Un <strong>grand</strong> voyage.</p>")
        self.assertEqual([j["date"] for j in d["jours"]], ["2025-06-01", "2025-06-02", "2025-06-03"])
        jour = d["jours"][1]
        self.assertEqual((jour["titre"], jour["lieu"], jour["nb_photos"], jour["recit_rempli"]), ("Jour 2", "Kyoto", 4, True))
        self.assertFalse(d["jours"][0]["recit_rempli"])
        self.assertEqual(set(jour["photo"]["rendus"]), {"miniature", "moyenne", "grande"})

    def test_photo_representative_d_un_jour(self):
        jour = self.voyage.jours.get(date=date(2025, 6, 1))
        favori = jour.photos.get(ordre=3)
        favori.favori = True
        favori.save()

        d = self.client.get("/api/voyages/japon-2025/").json()

        self.assertEqual(d["jours"][0]["photo"]["id"], favori.id)
        self.assertEqual(d["jours"][1]["photo"]["id"], self.voyage.jours.get(date=date(2025, 6, 2)).photos.get(ordre=1).id)

    def test_trace_ordonne_par_date_sans_photos_masquees(self):
        jour = self.voyage.jours.get(date=date(2025, 6, 2))
        masquee = creer_photo(jour, 9, gps=(10.0, 10.0), visible=False)

        trace = self.client.get("/api/voyages/japon-2025/").json()["trace"]

        self.assertTrue(trace)
        self.assertEqual([p["jour"] for p in trace], sorted(p["jour"] for p in trace))
        self.assertNotIn(masquee.latitude, [p["lat"] for p in trace])
        self.assertEqual(set(trace[0]), {"lat", "lon", "jour"})

    def test_aucune_donnee_sensible(self):
        contenu = self.client.get("/api/voyages/japon-2025/").content.decode()

        for cle in CHAMPS_INTERDITS:
            self.assertNotIn(f'"{cle}"', contenu)

    def test_voyage_inconnu(self):
        self.assertEqual(self.client.get("/api/voyages/nulle-part/").status_code, 404)


class DetailJourTests(TestCase):
    def setUp(self):
        self.voyage = creer_voyage(jours=3, photos=4)
        self.jour = self.voyage.jours.get(date=date(2025, 6, 2))

    def get(self, d="2025-06-02"):
        return self.client.get(f"/api/voyages/japon-2025/jours/{d}/")

    def test_recit_et_photos(self):
        self.jour.recit = "## Kyoto\n\nPluie."
        self.jour.lieu = "Kyoto"
        self.jour.save()

        d = self.get().json()

        self.assertEqual((d["date"], d["titre"], d["lieu"]), ("2025-06-02", "Jour 2", "Kyoto"))
        self.assertEqual(d["recit"], "## Kyoto\n\nPluie.")
        self.assertEqual(d["recit_html"], "<h2>Kyoto</h2>\n<p>Pluie.</p>")
        self.assertEqual(d["voyage"], {"slug": "japon-2025", "titre": "Japon 2025", "fuseau_horaire": "Asia/Tokyo"})
        photo = d["photos"][0]
        self.assertEqual(
            set(photo),
            {"id", "largeur", "hauteur", "couleur", "placeholder", "rendus", "prise_le", "legende", "favori",
             "photographe", "type", "duree", "videos"},
        )
        self.assertEqual((photo["type"], photo["duree"], photo["videos"]), ("photo", None, {}))
        self.assertEqual(photo["photographe"], "")
        self.assertEqual((photo["largeur"], photo["hauteur"], photo["couleur"]), (3000, 2000, "#336699"))
        self.assertEqual(photo["rendus"]["moyenne"]["url"], f"/media/rendus/{photo['id']}/abc-moyenne.webp")

    def test_video_et_photo_animee(self):
        creer_photo(self.jour, 5, type=Photo.Type.VIDEO, duree=54.12)
        creer_photo(self.jour, 6, type=Photo.Type.ANIMEE, duree=3.14)

        photos = {p["type"]: p for p in self.get().json()["photos"]}

        video = photos["video"]
        self.assertEqual(video["duree"], 54.12)
        self.assertEqual(video["videos"], {
            "720": {"url": f"/media/rendus/{video['id']}/abc-video_720.mp4", "largeur": 1080, "hauteur": 720},
            "1080": {"url": f"/media/rendus/{video['id']}/abc-video_1080.mp4", "largeur": 1620, "hauteur": 1080},
        })
        # L'aperçu (poster) : les rendus WebP, sans les MP4.
        self.assertEqual(set(video["rendus"]), {"miniature", "moyenne", "grande"})
        self.assertEqual(set(photos["animee"]["videos"]), {"720", "1080"})
        self.assertEqual(photos["animee"]["duree"], 3.14)

    def test_prise_le_dans_le_fuseau_du_voyage(self):
        # Photo 1 du 2 juin : 01:00 UTC → 10:00 à Tokyo.
        self.assertEqual(self.get().json()["photos"][0]["prise_le"], "2025-06-02T10:00:00+09:00")

    def test_photos_dans_l_ordre_choisi(self):
        p1, p2, p3, p4 = self.jour.photos.order_by("ordre")
        for photo, ordre in ((p3, 1), (p1, 2), (p4, 3), (p2, 4)):
            photo.ordre = ordre
            photo.save()

        self.assertEqual([p["id"] for p in self.get().json()["photos"]], [p3.id, p1.id, p4.id, p2.id])

    def test_heure_de_prise_departage_les_ordres_egaux(self):
        self.jour.photos.update(ordre=0)
        attendu = list(self.jour.photos.order_by("prise_le").values_list("id", flat=True))

        self.assertEqual([p["id"] for p in self.get().json()["photos"]], attendu)

    def test_photos_masquees_exclues(self):
        masquee = self.jour.photos.get(ordre=2)
        masquee.visible = False
        masquee.save()

        ids = [p["id"] for p in self.get().json()["photos"]]

        self.assertEqual(len(ids), 3)
        self.assertNotIn(masquee.id, ids)

    def test_precedent_et_suivant(self):
        d = self.get().json()

        self.assertEqual((d["precedent"]["date"], d["precedent"]["titre"]), ("2025-06-01", "Jour 1"))
        self.assertEqual(d["suivant"]["date"], "2025-06-03")
        self.assertEqual(set(d["suivant"]["photo"]), {"id", "largeur", "hauteur", "couleur", "placeholder", "rendus"})

    def test_extremites(self):
        self.assertIsNone(self.get("2025-06-01").json()["precedent"])
        self.assertIsNone(self.get("2025-06-03").json()["suivant"])

    def test_voisin_sans_photo_visible(self):
        self.voyage.jours.get(date=date(2025, 6, 3)).photos.update(visible=False)

        suivant = self.get().json()["suivant"]

        self.assertEqual(suivant["date"], "2025-06-03")
        self.assertIsNone(suivant["photo"])

    def test_jour_sans_media_visible_ni_recit_absent_du_site(self):
        # Photos WhatsApp sans date : masquées, rangées à la date du fichier.
        cache = Jour.objects.create(voyage=self.voyage, date=date(2025, 6, 12))
        creer_photo(cache, 1, visible=False)
        dernier = self.voyage.jours.get(date=date(2025, 6, 3))

        detail = self.client.get("/api/voyages/japon-2025/").json()
        self.assertNotIn("2025-06-12", [j["date"] for j in detail["jours"]])
        self.assertEqual(detail["nb_jours"], 3)
        self.assertEqual(self.client.get("/api/voyages/").json()[0]["nb_jours"], 3)
        self.assertIsNone(self.get("2025-06-03").json()["suivant"])
        self.assertEqual(self.get("2025-06-12").status_code, 404)

        # Un récit écrit suffit à le faire apparaître.
        cache.recit = "Retour."
        cache.save()
        self.assertEqual(self.get("2025-06-03").json()["suivant"]["date"], "2025-06-12")
        self.assertEqual(dernier.date, date(2025, 6, 3))

    def test_aucune_donnee_sensible(self):
        contenu = self.get().content.decode()

        for cle in CHAMPS_INTERDITS:
            self.assertNotIn(f'"{cle}"', contenu)

    def test_introuvable(self):
        self.assertEqual(self.get("2025-07-01").status_code, 404)  # pas de jour à cette date
        self.assertEqual(self.get("2025-13-45").status_code, 404)  # date impossible
        self.assertEqual(self.client.get("/api/voyages/japon-2025/jours/hier/").status_code, 404)
        self.assertEqual(self.client.get("/api/voyages/autre/jours/2025-06-02/").status_code, 404)


class NombreDeRequetesTests(TestCase):
    """Le nombre de requêtes de chaque endpoint ne dépend pas du volume de données."""

    ATTENDU = {
        "/api/voyages/": 4,  # voyages annotés, photos de couverture, rendus, couleurs (palettes)
        "/api/voyages/japon-2025/": 5,  # voyage, jours, photos, rendus, médias (tracé + palettes)
        "/api/voyages/japon-2025/jours/2025-06-02/": 6,  # jour, jours, photos, rendus, vignettes voisines, rendus
    }

    def compter(self, url):
        with CaptureQueriesContext(connection) as requetes:
            self.assertEqual(self.client.get(url).status_code, 200)
        return len(requetes)

    def test_nombre_fixe_quel_que_soit_le_volume(self):
        creer_voyage("japon-2025", jours=3, photos=4)
        creer_voyage("islande", jours=3, photos=4, debut=date(2024, 6, 1))
        petits = {url: self.compter(url) for url in self.ATTENDU}

        # Deux fois plus de voyages, de jours et de photos.
        creer_voyage("ecosse", jours=6, photos=8, debut=date(2023, 6, 1))
        creer_voyage("perou", jours=6, photos=8, debut=date(2022, 6, 1))
        japon = Jour.objects.get(voyage__slug="japon-2025", date=date(2025, 6, 2))
        for n in range(5, 13):
            creer_photo(japon, n)
        # Des vidéos et des photos animées : leurs MP4 ne coûtent aucune requête.
        for n, type_ in ((13, Photo.Type.VIDEO), (14, Photo.Type.ANIMEE), (15, Photo.Type.VIDEO)):
            creer_photo(japon, n, type=type_)
        grands = {url: self.compter(url) for url in self.ATTENDU}

        self.assertEqual(petits, self.ATTENDU)
        self.assertEqual(grands, self.ATTENDU)


class AccesTests(TestCase):
    def setUp(self):
        creer_voyage()
        self.urls = ["/api/voyages/", "/api/voyages/japon-2025/", "/api/voyages/japon-2025/jours/2025-06-01/"]

    def test_ouverte_sur_le_reseau_prive(self):
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    @override_settings(API_ACCES="connecte")
    def test_session_exigee_en_mode_connecte(self):
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.force_login(get_user_model().objects.create_user("lecteur"))
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_lecture_seule(self):
        self.client.force_login(get_user_model().objects.create_superuser("admin", password="x"))
        for url in self.urls:
            for methode in ("post", "put", "patch", "delete"):
                self.assertIn(getattr(self.client, methode)(url).status_code, (403, 405), f"{methode} {url}")
