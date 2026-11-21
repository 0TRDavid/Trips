"""Rendu Markdown → HTML nettoyé (API et aperçu de l'admin)."""

from django.test import SimpleTestCase

from voyages.markdown import apercu_recit, decouper_recit, recit_sans_marqueurs, rendre_markdown


class RendreMarkdownTests(SimpleTestCase):
    def test_rendu_de_base(self):
        html = rendre_markdown("## Kyoto\n\nLe matin, **Fushimi Inari**, *thé*.\n\n- un\n- deux\n\n> citation")

        self.assertIn("<h2>Kyoto</h2>", html)
        self.assertIn("<strong>Fushimi Inari</strong>", html)
        self.assertIn("<em>thé</em>", html)
        self.assertIn("<ul>\n<li>un</li>", html)
        self.assertIn("<blockquote>", html)

    def test_vide(self):
        self.assertEqual(rendre_markdown(""), "")
        self.assertEqual(rendre_markdown("  \n\n "), "")

    def test_html_brut_neutralise(self):
        html = rendre_markdown('Avant <script>alert(1)</script> <img src=x onerror="alert(2)"> après')

        # Le HTML écrit dans le récit reste du texte affiché, jamais une balise.
        self.assertNotIn("<script", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)

    def test_liens_javascript_retires(self):
        html = rendre_markdown("[clic](javascript:alert(1)) et [site](https://example.org)")

        # markdown-it refuse ce lien : il reste du texte inerte, jamais un href.
        self.assertNotIn('href="javascript', html)
        self.assertIn('href="https://example.org"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_balises_hors_liste_blanche_retirees(self):
        # Une image Markdown ne passe pas : les photos du récit viennent de la galerie, pas d'URL externes.
        html = rendre_markdown("![photo](https://example.org/a.jpg)")

        self.assertNotIn("<img", html)


class DecouperRecitTests(SimpleTestCase):
    """Marqueurs `[[14h]]` : le récit est découpé en blocs placés entre les photos."""

    def test_sans_marqueur_un_seul_bloc(self):
        self.assertEqual(decouper_recit("Une *belle* journée."), [{"heure": None, "html": "<p>Une <em>belle</em> journée.</p>"}])

    def test_vide(self):
        self.assertEqual(decouper_recit(""), [])
        self.assertEqual(decouper_recit("[[14h]]\n\n"), [])

    def test_intro_puis_heures(self):
        blocs = decouper_recit("Réveil tôt.\n\n[[10h]]\nLe temple.\n\n[[14h30]]\n\nLe marché.\n\nPuis le thé.")
        self.assertEqual([b["heure"] for b in blocs], [None, "10:00", "14:30"])
        self.assertEqual(blocs[1]["html"], "<p>Le temple.</p>")
        self.assertEqual(blocs[2]["html"], "<p>Le marché.</p>\n<p>Puis le thé.</p>")

    def test_variantes_d_ecriture(self):
        blocs = decouper_recit("[[ 9h ]]\na\n\n[[21H05]]\nb\n\n  [[7 h]]\nc")
        self.assertEqual([b["heure"] for b in blocs], ["09:00", "21:05", "07:00"])

    def test_marqueur_invalide_reste_du_texte(self):
        blocs = decouper_recit("[[25h]]\n\n[[14h75]]\n\nVoir [[14h]] au milieu d'une ligne.")
        self.assertEqual(len(blocs), 1)
        self.assertIsNone(blocs[0]["heure"])
        self.assertIn("[[25h]]", blocs[0]["html"])
        self.assertIn("[[14h]] au milieu", blocs[0]["html"])

    def test_ignore_dans_un_bloc_de_code(self):
        blocs = decouper_recit("```\n[[14h]]\n```\n\n[[15h]]\nApres.")
        self.assertEqual([b["heure"] for b in blocs], [None, "15:00"])
        self.assertIn("[[14h]]", blocs[0]["html"])

    def test_html_echappe_dans_chaque_bloc(self):
        blocs = decouper_recit("[[10h]]\n<script>alert(1)</script> ok")
        self.assertNotIn("<script", blocs[0]["html"])

    def test_recit_sans_marqueurs(self):
        self.assertEqual(recit_sans_marqueurs("A.\n\n[[10h]]\nB."), "<p>A.</p>\n<p>B.</p>")

    def test_apercu_montre_les_marqueurs(self):
        html = apercu_recit("A.\n\n[[10h]]\nB.\n\n[[14h30]]\nC.")
        self.assertIn('<p class="carnet-marqueur">⏱ 10 h</p>', html)
        self.assertIn("⏱ 14 h 30", html)
        self.assertNotIn("[[", html)
