"""Rendu Markdown → HTML nettoyé (API et aperçu de l'admin)."""

from django.test import SimpleTestCase

from voyages.markdown import rendre_markdown


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
