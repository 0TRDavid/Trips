"""Voyages, jours et photos créés directement en base, avec des rendus fictifs.

Pour les tests de l'API et de l'admin : ni Nextcloud, ni fichiers, seulement
des lignes en base (les URL des rendus pointent vers des fichiers inexistants).
"""

from datetime import date, datetime, timedelta, timezone

from django.contrib.auth import get_user_model

from voyages.models import Jour, Photo, Rendu, Voyage

TAILLES = {"miniature": 400, "moyenne": 1280, "grande": 2560}


def auteur():
    return get_user_model().objects.get_or_create(username="dd")[0]


def creer_photo(jour, n, *, heure=None, ordre=None, gps=None, **champs):
    """Photo n du jour, prise à 9 h + n heures (heure de Tokyo) si `heure` n'est pas donnée."""
    prise_le = heure or datetime.combine(jour.date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=n)
    # Comme un import : date et position lues dans les métadonnées.
    champs.setdefault("source_date", "exif")
    champs.setdefault("source_position", "exif" if gps else "")
    photo = Photo.objects.create(
        jour=jour,
        chemin_nextcloud=f"{jour.voyage.dossier_nextcloud}/{jour.date}-{n:03d}.jpg",
        etag=f"e{jour.pk}-{n}",
        rendus_etag=f"e{jour.pk}-{n}",
        prise_le=prise_le,
        latitude=gps[0] if gps else None,
        longitude=gps[1] if gps else None,
        altitude=12.0 if gps else None,
        ordre=n if ordre is None else ordre,
        largeur=3000,
        hauteur=2000,
        couleur="#336699",
        placeholder="AbCdEf",
        **champs,
    )
    for taille, cote in TAILLES.items():
        Rendu.objects.create(
            photo=photo, taille=taille, largeur=cote, hauteur=cote * 2 // 3, octets=1000,
            fichier=f"rendus/{photo.pk}/abc-{taille}.webp",
        )
    if photo.type != Photo.Type.PHOTO:  # photo animée ou vidéo : ses MP4
        for taille, cote in (("video_720", 720), ("video_1080", 1080)):
            Rendu.objects.create(
                photo=photo, taille=taille, format="mp4", largeur=cote * 3 // 2, hauteur=cote, octets=5000,
                fichier=f"rendus/{photo.pk}/abc-{taille}.mp4",
            )
    return photo


def creer_voyage(slug="japon-2025", *, jours=3, photos=4, debut=date(2025, 6, 1), gps=True):
    """Un voyage de `jours` jours, `photos` photos par jour, toutes avec GPS si demandé."""
    voyage = Voyage.objects.create(
        auteur=auteur(), titre=slug.replace("-", " ").title(), slug=slug,
        dossier_nextcloud=f"/Shared/{slug}", fuseau_horaire="Asia/Tokyo",
        date_debut=debut, date_fin=debut + timedelta(days=jours - 1),
    )
    for j in range(jours):
        jour = Jour.objects.create(voyage=voyage, date=debut + timedelta(days=j), titre=f"Jour {j + 1}")
        for n in range(1, photos + 1):
            position = (35.0 + j * 0.1 + n * 0.01, 139.0 + j * 0.1 + n * 0.013) if gps else None
            creer_photo(jour, n, gps=position)
    return voyage
