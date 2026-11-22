"""Rendu des récits Markdown en HTML nettoyé.

Un seul moteur pour tout le site : l'API, l'aperçu de l'éditeur dans l'admin,
et plus tard l'export. Le récit reste stocké en Markdown (lisible dans 20 ans) ;
le HTML n'est qu'une vue calculée à la demande.

markdown-it-py suit CommonMark ; le HTML brut écrit dans le récit est
désactivé, et nh3 (successeur de bleach) passe ensuite sur le résultat avec une
liste blanche : rien d'exécutable ne peut atteindre le navigateur.
"""

import re

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


# --- Récit intercalé entre les moments de la journée ---------------------------
# Une ligne seule `[[14h]]` ou `[[14h30]]` place le texte qui la suit (jusqu'au
# marqueur suivant) juste avant la première photo prise à cette heure ou après.
# Le placement se fait dans le front (lib/recit.ts), sur l'ordre des photos ;
# le serveur ne fait que découper et rendre chaque morceau avec le même moteur.

_MARQUEUR = re.compile(r"^\s{0,3}\[\[\s*(\d{1,2})\s*h\s*(\d{2})?\s*\]\]\s*$", re.IGNORECASE)
_CLOTURE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


def _heure_du_marqueur(ligne: str) -> str | None:
    """`[[14h30]]` → "14:30" ; None si la ligne n'est pas un marqueur valide."""
    m = _MARQUEUR.match(ligne)
    if not m:
        return None
    heures, minutes = int(m.group(1)), int(m.group(2) or 0)
    if heures > 23 or minutes > 59:
        return None
    return f"{heures:02d}:{minutes:02d}"


def _morceaux(texte: str) -> list[tuple[str | None, str]]:
    """Découpe le Markdown aux lignes de marqueur (hors blocs de code clôturés)."""
    morceaux: list[tuple[str | None, list[str]]] = [(None, [])]
    cloture: str | None = None
    for ligne in (texte or "").splitlines():
        c = _CLOTURE.match(ligne)
        if c:
            signe = c.group(1)[0]
            if cloture is None:
                cloture = signe
            elif cloture == signe:
                cloture = None
        heure = None if cloture or c else _heure_du_marqueur(ligne)
        if heure is not None:
            morceaux.append((heure, []))
        else:
            morceaux[-1][1].append(ligne)
    return [(heure, "\n".join(lignes)) for heure, lignes in morceaux]


def decouper_recit(texte: str) -> list[dict]:
    """Récit → blocs `{"heure": "14:30" | None, "html": …}` dans l'ordre d'écriture.

    Le premier bloc (heure None) est le texte écrit avant tout marqueur. Les
    blocs vides sont omis : sans marqueur, on obtient un seul bloc (ou aucun).
    """
    blocs = []
    for heure, morceau in _morceaux(texte):
        html = rendre_markdown(morceau)
        if html:
            blocs.append({"heure": heure, "html": html})
    return blocs


def recit_sans_marqueurs(texte: str) -> str:
    """Le récit en HTML d'un seul tenant, lignes de marqueur retirées."""
    return "\n".join(b["html"] for b in decouper_recit(texte))


def apercu_recit(texte: str) -> str:
    """Aperçu de l'admin : chaque marqueur devient une étiquette « ⏱ 14 h 30 »."""
    parties = []
    for heure, morceau in _morceaux(texte):
        if heure is not None:
            h, m = heure.split(":")
            libelle = f"{int(h)} h {m}" if m != "00" else f"{int(h)} h"
            parties.append(f'<p class="carnet-marqueur">⏱ {libelle}</p>')
        html = rendre_markdown(morceau)
        if html:
            parties.append(html)
    return "\n".join(parties)
