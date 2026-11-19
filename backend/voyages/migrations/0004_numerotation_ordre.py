"""Numérote `Photo.ordre` (1, 2, 3…) dans chaque jour, selon l'heure de prise de vue.

Jusqu'ici toutes les photos avaient ordre = 0 et l'ordre venait de `prise_le` :
l'ordre affiché ne change donc pas, mais le glisser-déposer de l'admin a
désormais des valeurs distinctes à permuter.
"""

from django.db import migrations


def numeroter(apps, schema_editor):
    Photo = apps.get_model("voyages", "Photo")
    jour_courant, rang, a_modifier = None, 0, []
    for photo in Photo.objects.order_by("jour_id", "ordre", "prise_le", "id"):
        if photo.jour_id != jour_courant:
            jour_courant, rang = photo.jour_id, 0
        rang += 1
        if photo.ordre != rang:
            photo.ordre = rang
            a_modifier.append(photo)
    Photo.objects.bulk_update(a_modifier, ["ordre"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("voyages", "0003_libelles_francais"),
    ]

    operations = [
        migrations.RunPython(numeroter, migrations.RunPython.noop),
    ]
