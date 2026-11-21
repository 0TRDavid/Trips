"""Sources de la date et de la position des médias déjà importés.

- Position : « exif » quand une latitude est connue.
- Date : les médias masqués à l'import l'ont été faute de date (date du fichier,
  provisoire) → aucune source ; une vidéo dont le nom porte la date, dans un
  voyage qui lit les dates dans les noms (« nom de fichier ») → « nom_fichier » ;
  le reste vient des métadonnées → « exif ».
Le prochain import recalculera tout ce qui n'est pas saisi à la main.
"""

import posixpath
import re

from django.db import migrations

NOM_DATE = re.compile(r"^(\d{2})-(\d{2})-(\d{2}) (\d{2})-(\d{2})-(\d{2})(?!\d)")


def remplir(apps, schema_editor):
    Photo = apps.get_model("voyages", "Photo")
    Photo.objects.filter(latitude__isnull=False).update(source_position="exif")
    Photo.objects.filter(visible=True).update(source_date="exif")
    for photo in Photo.objects.filter(visible=True, type="video").select_related("jour__voyage"):
        horloges = photo.jour.voyage.horloges_appareils or {}
        if "nom de fichier" in horloges and NOM_DATE.match(posixpath.basename(photo.chemin_nextcloud)):
            photo.source_date = "nom_fichier"
            photo.save(update_fields=["source_date"])


class Migration(migrations.Migration):
    dependencies = [("voyages", "0007_completion")]
    operations = [migrations.RunPython(remplir, migrations.RunPython.noop)]
