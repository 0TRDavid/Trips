"""Ordre des photos : numérotation initiale (migration) et import qui le respecte."""

import importlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from voyages.importation import importer_voyage
from voyages.models import Photo

from .donnees import creer_voyage
from .test_importation import DOSSIER, FauxClient, photo_tokyo

migration = importlib.import_module("voyages.migrations.0004_numerotation_ordre")


class NumerotationTests(TestCase):
    def test_numerote_chaque_jour_selon_l_heure_de_prise(self):
        voyage = creer_voyage(jours=2, photos=3)
        Photo.objects.update(ordre=0)
        # Mélange les heures du premier jour : l'ordre doit suivre prise_le, pas l'id.
        jour = voyage.jours.order_by("date").first()
        a, b, c = jour.photos.order_by("id")
        a.prise_le, c.prise_le = c.prise_le, a.prise_le
        a.save()
        c.save()

        migration.numeroter(apps, None)

        self.assertEqual(list(jour.photos.order_by("ordre").values_list("id", "ordre")), [(c.id, 1), (b.id, 2), (a.id, 3)])
        autre = voyage.jours.order_by("date").last()
        self.assertEqual(list(autre.photos.order_by("prise_le").values_list("ordre", flat=True)), [1, 2, 3])


class ImportOrdreTests(TestCase):
    def setUp(self):
        self.auteur = get_user_model().objects.create_user("dd")

    def importer(self, client):
        return importer_voyage(client, DOSSIER, fuseau="Asia/Tokyo", auteur=self.auteur)

    def test_nouvelles_photos_a_la_suite_sans_toucher_l_ordre_choisi(self):
        fichiers = {
            "a.jpg": ("1", photo_tokyo("09:00:00")),
            "b.jpg": ("2", photo_tokyo("10:00:00")),
        }
        self.importer(FauxClient(fichiers))
        a, b = Photo.objects.order_by("prise_le")
        self.assertEqual((a.ordre, b.ordre), (1, 2))
        # L'auteur inverse l'ordre dans l'admin.
        Photo.objects.filter(pk=a.pk).update(ordre=2)
        Photo.objects.filter(pk=b.pk).update(ordre=1)

        # Nouvelle photo synchronisée (prise avant les autres) + b modifiée dans Nextcloud.
        fichiers["c.jpg"] = ("3", photo_tokyo("08:00:00"))
        fichiers["b.jpg"] = ("2bis", photo_tokyo("10:00:00"))
        self.importer(FauxClient(fichiers))

        ordres = dict(Photo.objects.values_list("chemin_nextcloud", "ordre"))
        self.assertEqual(ordres, {f"{DOSSIER}/a.jpg": 2, f"{DOSSIER}/b.jpg": 1, f"{DOSSIER}/c.jpg": 3})

    def test_photo_qui_change_de_jour_va_a_la_fin_du_nouveau_jour(self):
        fichiers = {
            "a.jpg": ("1", photo_tokyo("09:00:00", jour=5)),
            "b.jpg": ("2", photo_tokyo("10:00:00", jour=6)),
        }
        self.importer(FauxClient(fichiers))
        fichiers["a.jpg"] = ("1bis", photo_tokyo("12:00:00", jour=6))  # date corrigée dans Nextcloud

        self.importer(FauxClient(fichiers))

        a = Photo.objects.get(chemin_nextcloud=f"{DOSSIER}/a.jpg")
        self.assertEqual((str(a.jour.date), a.ordre), ("2025-04-06", 2))
