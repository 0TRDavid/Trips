"""Admin : pages, récit, ordre par glisser-déposer, couverture, aperçu, régénération."""

from datetime import date
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from voyages.admin import lancer_regeneration
from voyages.generation import photos_a_traiter
from voyages.models import Jour, Photo

from .donnees import creer_voyage


class AdminTests(TestCase):
    def setUp(self):
        self.voyage = creer_voyage(jours=3, photos=4)
        self.jour = self.voyage.jours.get(date=date(2025, 6, 2))
        self.client.force_login(get_user_model().objects.create_superuser("admin", password="x"))

    def formulaire_jour(self, **modifs):
        """Données POST du formulaire d'un jour, avec le formset des photos dans l'ordre actuel."""
        photos = list(self.jour.photos.order_by("ordre"))
        donnees = {
            "titre": self.jour.titre, "lieu": self.jour.lieu, "recit": self.jour.recit,
            "photos-TOTAL_FORMS": len(photos), "photos-INITIAL_FORMS": len(photos),
            "photos-MIN_NUM_FORMS": 0, "photos-MAX_NUM_FORMS": 1000,
        }
        for i, photo in enumerate(photos):
            donnees |= {
                f"photos-{i}-id": photo.id, f"photos-{i}-jour": self.jour.id, f"photos-{i}-ordre": photo.ordre,
                f"photos-{i}-legende": photo.legende, f"photos-{i}-visible": "on",
            }
        donnees.update(modifs)
        return donnees, photos

    def test_pages_principales(self):
        urls = [
            reverse("admin:index"),
            reverse("admin:voyages_voyage_changelist"),
            reverse("admin:voyages_voyage_change", args=[self.voyage.pk]),
            reverse("admin:voyages_jour_changelist"),
            reverse("admin:voyages_jour_changelist") + "?recit=non",
            reverse("admin:voyages_jour_change", args=[self.jour.pk]),
            reverse("admin:voyages_photo_changelist"),
            reverse("admin:voyages_photo_change", args=[self.jour.photos.first().pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_interface_en_francais(self):
        contenu = self.client.get(reverse("admin:voyages_jour_changelist")).content.decode()

        self.assertIn("Carnet de voyages", contenu)
        self.assertIn("récit écrit", contenu.lower())

    def test_liste_des_jours_nombre_de_photos_et_recit(self):
        Jour.objects.filter(pk=self.jour.pk).update(recit="Écrit.")
        Photo.objects.filter(jour=self.jour, ordre=1).update(visible=False)

        reponse = self.client.get(reverse("admin:voyages_jour_changelist") + "?recit=non")
        jours = list(reponse.context["cl"].result_list)

        self.assertEqual([j.date for j in jours], [date(2025, 6, 1), date(2025, 6, 3)])
        self.assertContains(
            self.client.get(reverse("admin:voyages_jour_changelist")), "4 (dont 1 masquée)"
        )

    def test_ecrire_le_recit_d_un_jour(self):
        donnees, _ = self.formulaire_jour(titre="Kyoto", lieu="Fushimi", recit="## Pluie\r\n\r\nThé à l'été.")

        reponse = self.client.post(reverse("admin:voyages_jour_change", args=[self.jour.pk]), donnees)

        self.assertEqual(reponse.status_code, 302, reponse.context and reponse.context["errors"])
        self.jour.refresh_from_db()
        self.assertEqual((self.jour.titre, self.jour.lieu), ("Kyoto", "Fushimi"))
        self.assertEqual(self.jour.recit, "## Pluie\n\nThé à l'été.")  # fins de ligne normalisées

    def test_reordonner_les_photos_et_legender(self):
        donnees, (p1, p2, p3, p4) = self.formulaire_jour()
        # Ce que fait le glisser-déposer : il réécrit les champs « ordre » cachés.
        donnees |= {"photos-0-ordre": 3, "photos-1-ordre": 1, "photos-2-ordre": 4, "photos-3-ordre": 2}
        donnees |= {"photos-1-legende": "Le torii", "photos-1-favori": "on"}
        del donnees["photos-3-visible"]

        reponse = self.client.post(reverse("admin:voyages_jour_change", args=[self.jour.pk]), donnees)

        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(list(self.jour.photos.order_by("ordre")), [p2, p4, p1, p3])
        p2.refresh_from_db()
        p4.refresh_from_db()
        self.assertEqual((p2.legende, p2.favori), ("Le torii", True))
        self.assertFalse(p4.visible)

        api = self.client.get("/api/voyages/japon-2025/jours/2025-06-02/").json()
        self.assertEqual([p["id"] for p in api["photos"]], [p2.id, p1.id, p3.id])  # p4 masquée

    def test_navigation_entre_jours(self):
        reponse = self.client.get(reverse("admin:voyages_jour_change", args=[self.jour.pk]))

        self.assertEqual(reponse.context["jour_precedent"].date, date(2025, 6, 1))
        self.assertEqual(reponse.context["jour_suivant"].date, date(2025, 6, 3))

    def test_choisir_la_couverture_parmi_les_photos_du_voyage(self):
        autre = creer_voyage("islande", jours=1, photos=1)
        url = reverse("admin:voyages_voyage_change", args=[self.voyage.pk])
        reponse = self.client.get(url)
        choix = reponse.context["adminform"].form.fields["couverture"].queryset

        self.assertEqual(set(choix), set(Photo.objects.filter(jour__voyage=self.voyage)))
        self.assertContains(reponse, "abc-miniature.webp")

        photo = self.jour.photos.get(ordre=2)
        donnees = {
            "titre": "Japon", "slug": "japon-2025", "date_debut": "2025-06-01", "date_fin": "2025-06-03",
            "fuseau_horaire": "Asia/Tokyo", "couverture": photo.pk, "recit_intro": "Intro\r\nSuite",
            "jours-TOTAL_FORMS": 0, "jours-INITIAL_FORMS": 0, "jours-MIN_NUM_FORMS": 0, "jours-MAX_NUM_FORMS": 0,
        }
        self.assertEqual(self.client.post(url, donnees).status_code, 302)
        self.voyage.refresh_from_db()
        self.assertEqual((self.voyage.couverture, self.voyage.recit_intro), (photo, "Intro\nSuite"))

        # Une photo d'un autre voyage est refusée.
        donnees["couverture"] = autre.jours.get().photos.get().pk
        self.assertEqual(self.client.post(url, donnees).status_code, 200)

    def test_fuseau_invalide_refuse(self):
        url = reverse("admin:voyages_voyage_change", args=[self.voyage.pk])
        donnees = {
            "titre": "Japon", "slug": "japon-2025", "fuseau_horaire": "Mars/Olympus",
            "jours-TOTAL_FORMS": 0, "jours-INITIAL_FORMS": 0, "jours-MIN_NUM_FORMS": 0, "jours-MAX_NUM_FORMS": 0,
        }
        reponse = self.client.post(url, donnees)

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("fuseau_horaire", reponse.context["adminform"].form.errors)

    def test_ni_creation_ni_suppression_de_voyage_ou_de_jour(self):
        self.assertEqual(self.client.get(reverse("admin:voyages_voyage_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:voyages_jour_add")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("admin:voyages_jour_delete", args=[self.jour.pk])).status_code, 403
        )

    def test_apercu_markdown(self):
        url = reverse("admin:voyages_apercu_markdown")

        reponse = self.client.post(url, {"texte": "**gras** <script>x</script>"})

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()["html"], "<p><strong>gras</strong> &lt;script&gt;x&lt;/script&gt;</p>")
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_apercu_reserve_a_l_equipe(self):
        self.client.logout()
        reponse = self.client.post(reverse("admin:voyages_apercu_markdown"), {"texte": "x"})

        self.assertEqual(reponse.status_code, 302)  # redirigé vers la connexion

    def test_action_regenerer_les_rendus(self):
        cas = [
            ("voyage", [self.voyage.pk], "regenerer_voyages", 12),
            ("jour", [self.jour.pk], "regenerer_jours", 4),
            ("photo", list(self.jour.photos.values_list("pk", flat=True)[:2]), "regenerer_photos", 2),
        ]
        for modele, selection, action, attendu in cas:
            with self.subTest(modele=modele), mock.patch("voyages.admin.lancer_regeneration") as lancer:
                reponse = self.client.post(
                    reverse(f"admin:voyages_{modele}_changelist"),
                    {"action": action, "_selected_action": selection},
                    follow=True,
                )
                lancer.assert_called_once()
                self.assertEqual(len(lancer.call_args.args[0]), attendu)
                self.assertContains(reponse, f"Régénération de {attendu} photos lancée")

    def test_lancer_regeneration_commande(self):
        with mock.patch("voyages.admin.subprocess.Popen") as popen:
            lancer_regeneration([12, 3, 7])

        commande = popen.call_args.args[0]
        self.assertEqual(commande[2:], ["generer_rendus", "--force", "--photos", "3,7,12"])
        self.assertTrue(commande[1].endswith("manage.py"))
        self.assertTrue(popen.call_args.kwargs["start_new_session"])


class GenererRendusPhotosTests(TestCase):
    def test_option_photos_limite_la_selection(self):
        creer_voyage(jours=1, photos=3)
        ids = list(Photo.objects.order_by("id").values_list("id", flat=True))
        sortie = StringIO()

        call_command("generer_rendus", "--dry-run", "--force", "--photos", f"{ids[0]},{ids[2]}", stdout=sortie)

        self.assertIn("Rendus web à générer : 2 (sur 2 photos)", sortie.getvalue())
        a_faire, total = photos_a_traiter(force=True, photos_ids=[ids[0], ids[2]])
        self.assertEqual(([p.id for p in a_faire], total), ([ids[0], ids[2]], 2))
