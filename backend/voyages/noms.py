"""Dates lues dans les noms de fichiers.

WhatsApp renomme les médias reçus : `IMG-20250604-WA0012.jpg`,
`VID-20250611-WA0075.mp4`. La date du nom est celle de **réception** (ou
d'enregistrement), pas forcément celle de la prise de vue : elle sert de
proposition, marquée « à confirmer ». Le numéro WAnnnn suit l'ordre d'arrivée.
"""

from __future__ import annotations

import posixpath
import re
from datetime import date, datetime, time, timezone, tzinfo

_WHATSAPP = re.compile(r"^(?:IMG|VID)-(\d{4})(\d{2})(\d{2})-WA(\d+)", re.IGNORECASE)
ANNEE_MIN = 1990
HEURE_PAR_DEFAUT = time(12, 0)


def analyser_whatsapp(nom: str) -> tuple[date, int] | None:
    """« …/IMG-20250604-WA0012.jpg » → (date(2025, 6, 4), 12) ; None sinon."""
    correspondance = _WHATSAPP.match(posixpath.basename(nom))
    if not correspondance:
        return None
    annee, mois, jour, numero = (int(v) for v in correspondance.groups())
    try:
        jour_nom = date(annee, mois, jour)
    except ValueError:
        return None
    if annee < ANNEE_MIN:
        return None
    return jour_nom, numero


def est_whatsapp(nom: str) -> bool:
    return analyser_whatsapp(nom) is not None


def proposer_date_whatsapp(nom: str, modifie_le: datetime | None, fuseau: tzinfo) -> datetime | None:
    """Date proposée (UTC) pour un média WhatsApp, ou None si le nom ne s'y prête pas.

    Le jour vient du nom ; l'heure est celle du fichier (l'heure de réception)
    quand elle tombe ce jour-là dans le fuseau du voyage, sinon midi.
    """
    analyse = analyser_whatsapp(nom)
    if analyse is None:
        return None
    jour_nom, _ = analyse
    heure = HEURE_PAR_DEFAUT
    if modifie_le is not None:
        locale = modifie_le.astimezone(fuseau)
        if locale.date() == jour_nom:
            heure = locale.time().replace(microsecond=0)
    return datetime.combine(jour_nom, heure, tzinfo=fuseau).astimezone(timezone.utc)
