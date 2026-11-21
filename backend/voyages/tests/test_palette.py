"""Palettes tirées des photos : couleurs vives, teintes, contrastes WCAG AA."""

from io import StringIO
from itertools import product

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from PIL import Image, ImageDraw

from voyages.models import Photo, Rendu
from voyages.palette import AA, Oklch, contraste, couleurs_vives, palette

from .donnees import creer_photo, creer_voyage
from .fabrique import CacheTemporaire

ROUGE_TORII = "#d23a2a"
VERT_BAMBOU = "#4f8a32"
BLEU_CIEL = "#3c7fd0"


def image_avec(fond: str, tache: str | None = None, part: float = 0.1) -> Image.Image:
    """Image de 100 × 100 : un fond, et éventuellement une tache couvrant `part`."""
    img = Image.new("RGB", (100, 100), fond)
    if tache:
        cote = round(100 * part**0.5)
        ImageDraw.Draw(img).rectangle((0, 0, cote - 1, cote - 1), fill=tache)
    return img


def teinte(hex_: str) -> float:
    return Oklch.depuis_hex(hex_).h


def ecart(h1: float, h2: float) -> float:
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


class ConversionsTests(SimpleTestCase):
    def test_aller_retour_hex_oklch(self):
        for hex_ in ("#000000", "#ffffff", ROUGE_TORII, VERT_BAMBOU, BLEU_CIEL, "#808080"):
            self.assertEqual(Oklch.depuis_hex(hex_).hex(), hex_)

    def test_contraste_wcag(self):
        self.assertAlmostEqual(contraste("#000000", "#ffffff"), 21, places=1)
        self.assertAlmostEqual(contraste("#777777", "#ffffff"), 4.48, places=2)

    def test_hors_gamut_ramene_sans_changer_la_teinte(self):
        trop_vif = Oklch(0.7, 0.4, 150)
        self.assertFalse(trop_vif.dans_le_gamut())
        ramene = trop_vif.ramener()
        self.assertTrue(ramene.dans_le_gamut())
        self.assertEqual((ramene.L, ramene.h), (0.7, 150))


class CouleursVivesTests(SimpleTestCase):
    def test_une_petite_tache_vive_l_emporte_sur_un_grand_fond_gris(self):
        couleurs = couleurs_vives(image_avec("#9d9d98", ROUGE_TORII, part=0.08))
        self.assertLess(ecart(teinte(couleurs[0]["hex"]), teinte(ROUGE_TORII)), 10)
        self.assertAlmostEqual(couleurs[0]["part"], 0.08, delta=0.03)

    def test_image_grise_sans_couleur_vive(self):
        self.assertEqual(couleurs_vives(image_avec("#9d9d98", "#414240", part=0.5)), [])

    def test_ombres_et_hautes_lumieres_ecartees(self):
        self.assertEqual(couleurs_vives(image_avec("#0a0d1a", "#fdfcf6", part=0.5)), [])

    def test_au_plus_cinq_couleurs(self):
        img = Image.new("RGB", (80, 80))
        dessin = ImageDraw.Draw(img)
        for i, c in enumerate(("#d23a2a", "#4f8a32", "#3c7fd0", "#d9a520", "#9a3fc0", "#2aa5a0", "#e0608a", "#7a5a20")):
            dessin.rectangle((i * 10, 0, i * 10 + 9, 79), fill=c)
        self.assertLessEqual(len(couleurs_vives(img)), 5)


class PaletteTests(SimpleTestCase):
    CLES = {"accent", "accent_texte", "sur_accent", "fond", "fond_2", "degrade"}

    def verifier_contrastes(self, p):
        for texte, fond in ((p["accent_texte"], p["fond"]), (p["accent_texte"], p["fond_2"]),
                            (p["sur_accent"], p["accent"]), ("#1d1b18", p["fond"]), ("#1d1b18", p["fond_2"])):
            self.assertGreaterEqual(contraste(texte, fond), AA, f"{texte} sur {fond}")

    def test_accent_de_la_teinte_dominante_et_degrade_varie(self):
        p = palette([
            ([{"hex": ROUGE_TORII, "part": 0.2}], 1),
            ([{"hex": ROUGE_TORII, "part": 0.1}, {"hex": VERT_BAMBOU, "part": 0.1}], 1),
            ([{"hex": BLEU_CIEL, "part": 0.05}], 1),
        ])
        self.assertEqual(set(p), self.CLES)
        self.assertLess(ecart(teinte(p["accent"]), teinte(ROUGE_TORII)), 20)
        self.assertEqual(len(p["degrade"]), 3)
        self.verifier_contrastes(p)

    def test_le_poids_d_une_couverture_fait_basculer_l_accent(self):
        medias = [([{"hex": VERT_BAMBOU, "part": 0.2}], 1), ([{"hex": BLEU_CIEL, "part": 0.15}], 1)]
        self.assertLess(ecart(teinte(palette(medias)["accent"]), teinte(VERT_BAMBOU)), 20)
        medias[1] = (medias[1][0], 3)
        self.assertLess(ecart(teinte(palette(medias)["accent"]), teinte(BLEU_CIEL)), 20)

    def test_sans_couleur_palette_neutre_complete(self):
        for medias in ([], [([], 1)], [([], 1), ([], 3)]):
            p = palette(medias)
            self.assertEqual(set(p), self.CLES)
            self.assertGreaterEqual(len(p["degrade"]), 2)
            self.verifier_contrastes(p)

    def test_contrastes_aa_sur_tout_le_cercle_et_toutes_les_luminosites(self):
        for h, L, C in product(range(0, 360, 15), (0.3, 0.5, 0.7, 0.9), (0.06, 0.15, 0.3)):
            couleur = Oklch(L, C, h).hex()
            with self.subTest(couleur=couleur):
                self.verifier_contrastes(palette([([{"hex": couleur, "part": 0.3}], 1)]))

    def test_accent_reste_vif(self):
        """Un orange sombre de la photo donne un accent franc, pas un brun."""
        p = palette([([{"hex": "#7a4318", "part": 0.3}], 1)])
        self.assertGreaterEqual(Oklch.depuis_hex(p["accent"]).L, 0.6)
        self.assertGreaterEqual(Oklch.depuis_hex(p["accent"]).C, 0.1)


class PaletteApiTests(TestCase):
    def setUp(self):
        self.voyage = creer_voyage(jours=2, photos=2)
        Photo.objects.filter(jour__date="2025-06-01").update(couleurs=[{"hex": ROUGE_TORII, "part": 0.2}])
        Photo.objects.filter(jour__date="2025-06-02").update(couleurs=[{"hex": BLEU_CIEL, "part": 0.2}])

    def test_palettes_du_voyage_et_des_jours(self):
        v = self.client.get("/api/voyages/").json()[0]
        self.assertEqual(set(v["palette"]), PaletteTests.CLES)

        detail = self.client.get("/api/voyages/japon-2025/").json()
        self.assertEqual(detail["palette"], v["palette"])
        rouge, bleu = (j["palette"]["accent"] for j in detail["jours"])
        self.assertLess(ecart(teinte(rouge), teinte(ROUGE_TORII)), 20)
        self.assertLess(ecart(teinte(bleu), teinte(BLEU_CIEL)), 20)

        jour = self.client.get("/api/voyages/japon-2025/jours/2025-06-02/").json()
        self.assertEqual(jour["palette"], detail["jours"][1]["palette"])

    def test_medias_masques_ignores(self):
        Photo.objects.filter(jour__date="2025-06-02").update(visible=False)
        creer_photo(self.voyage.jours.get(date="2025-06-02"), 9, couleurs=[{"hex": VERT_BAMBOU, "part": 0.2}])
        jour = self.client.get("/api/voyages/japon-2025/jours/2025-06-02/").json()
        self.assertLess(ecart(teinte(jour["palette"]["accent"]), teinte(VERT_BAMBOU)), 20)


class CommandeCouleursTests(CacheTemporaire, TestCase):
    def setUp(self):
        super().setUp()
        voyage = creer_voyage(jours=1, photos=2)
        self.photos = list(Photo.objects.filter(jour__voyage=voyage).order_by("ordre"))
        for photo, tache in zip(self.photos, (ROUGE_TORII, None)):
            rendu = Rendu.objects.get(photo=photo, taille="miniature")
            (self.cache / rendu.fichier).parent.mkdir(parents=True, exist_ok=True)
            image_avec("#9d9d98", tache, part=0.2).save(self.cache / rendu.fichier, "WEBP")

    def lancer(self, *args):
        sortie = StringIO()
        call_command("calculer_couleurs", *args, stdout=sortie)
        return sortie.getvalue()

    def test_calcule_depuis_la_miniature_et_ne_refait_que_si_demande(self):
        self.assertIn("Couleurs calculées : 2", self.lancer())
        rouge, gris = (Photo.objects.get(pk=p.pk) for p in self.photos)
        self.assertLess(ecart(teinte(rouge.couleurs[0]["hex"]), teinte(ROUGE_TORII)), 10)
        self.assertEqual(gris.couleurs, [])
        # Relance : seule la photo sans couleur vive est relue ; --force relit tout.
        self.assertIn("Couleurs calculées : 1", self.lancer())
        self.assertIn("Couleurs calculées : 2", self.lancer("--force"))

    def test_miniature_absente_signalee(self):
        Rendu.objects.filter(photo=self.photos[1]).delete()
        sortie = self.lancer()
        self.assertIn("Couleurs calculées : 1", sortie)
        self.assertIn("Sans miniature en cache", sortie)
