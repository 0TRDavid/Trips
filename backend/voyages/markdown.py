"""Rendu des récits Markdown en HTML nettoyé.

Un seul moteur pour tout le site : l'API, l'aperçu de l'éditeur dans l'admin,
et plus tard l'export. Le récit reste stocké en Markdown (lisible dans 20 ans) ;
le HTML n'est qu'une vue calculée à la demande.

markdown-it-py suit CommonMark ; le HTML brut écrit dans le récit est
désactivé, et nh3 (successeur de bleach) passe ensuite sur le résultat avec une
liste blanche : rien d'exécutable ne peut atteindre le navigateur.
"""

import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": False, "linkify": False, "typographer": False}).enable(
    "strikethrough"
)

BALISES = {
    "p", "br", "hr", "h2", "h3", "h4", "em", "strong", "s", "del", "a",
    "ul", "ol", "li", "blockquote", "code", "pre",
}
ATTRIBUTS = {"a": {"href", "title"}, "ol": {"start"}}
PROTOCOLES = {"http", "https", "mailto"}


def rendre_markdown(texte: str) -> str:
    """Markdown → HTML sûr. Une chaîne vide donne une chaîne vide."""
    if not texte or not texte.strip():
        return ""
    html = _md.render(texte)
    return nh3.clean(
        html,
        tags=BALISES,
        attributes=ATTRIBUTS,
        url_schemes=PROTOCOLES,
        link_rel="noopener noreferrer",
    ).strip()
