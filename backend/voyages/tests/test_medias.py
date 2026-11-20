"""Photos animées et vidéos : détection, métadonnées, rendus sans GPS, relance."""

import json
import shutil
import subprocess
from datetime import date, datetime, timezone
from unittest import skipUnless
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from voyages.generation import generer_rendus
from voyages.importation import VERSION_ANALYSE, importer_voyage
from voyages.models import Photo
from voyages.rendus_video import plan_tailles, produire_videos
from voyages.video import (
    Entree,
    date_du_nom,
    entree_memoire,
    infos_video,
    metadonnees_video,
    sonder,
    video_embarquee,
)

from .fabrique import FFMPEG, CacheTemporaire, boite, image, photo_animee, video
from .test_importation import DOSSIER, FauxClient

EXIFTOOL = shutil.which("exiftool")
TOKYO = ZoneInfo("Asia/Tokyo")
PARIS = ZoneInfo("Europe/Paris")


def sonde_de(octets: bytes) -> dict:
    with entree_memoire(octets) as entree:
        return sonder(entree)


# --- Photo animée : la boîte mpvd ------------------------------------------------

class VideoEmbarqueeTests(SimpleTestCase):
    def test_trouve_le_mp4_apres_l_image(self):
        mp4 = b"\x00\x00\x00\x18ftypmp42" + b"x" * 100
        octets = boite(b"ftyp", b"heic") + boite(b"mdat", b"i" * 50) + boite(b"meta", b"m") + boite(b"mpvd", mp4) + boite(b"sefd", b"s")
        position = video_embarquee(octets)
        self.assertEqual(octets[position], mp4)

    def test_boite_de_taille_64_bits(self):
        mp4 = b"video" * 10
        octets = boite(b"ftyp", b"heic") + boite(b"mdat", b"i" * 50, taille_64_bits=True) + boite(b"mpvd", mp4, taille_64_bits=True)
        self.assertEqual(octets[video_embarquee(octets)], mp4)

    def test_boite_qui_va_jusqu_a_la_fin(self):
        octets = boite(b"ftyp", b"heic") + b"\x00\x00\x00\x00mpvd" + b"video"
        self.assertEqual(octets[video_embarquee(octets)], b"video")

    def test_photo_sans_video(self):
        self.assertIsNone(video_embarquee(image("HEIF")))
        self.assertIsNone(video_embarquee(boite(b"ftyp", b"heic") + boite(b"mdat", b"i") + boite(b"sefd", b"s")))

    def test_fichier_tronque_ou_abime(self):
        complet = boite(b"ftyp", b"heic") + boite(b"mpvd", b"video" * 10)
        self.assertIsNone(video_embarquee(complet[:-5]))  # mpvd annonce plus que ce qui reste
        self.assertIsNone(video_embarquee(complet[:3]))
        self.assertIsNone(video_embarquee(b"\x00\x00\x00\x04mpvd"))  # taille < en-tête
        self.assertIsNone(video_embarquee(b""))

    @skipUnless(FFMPEG, "ffmpeg absent")
    def test_photo_animee_synthetique_lisible_par_ffprobe(self):
        clip = video(duree=0.5, taille=(160, 120), location=None)
        octets = photo_animee(clip)
        self.assertEqual(octets[video_embarquee(octets)], clip)
        infos = infos_video(sonde_de(octets[video_embarquee(octets)]))
        self.assertEqual((infos.largeur, infos.hauteur), (160, 120))


@skipUnless(settings.NEXTCLOUD_URL and settings.NEXTCLOUD_PASSWORD and FFMPEG, "Nextcloud non configuré")
class VraiePhotoAnimeeTests(SimpleTestCase):
    """Sur un vrai fichier du S24 (lu en mémoire, jamais commité ni écrit) :
    exiftool y voit `QuickTime:MotionPhotoVideo` de 4 500 927 octets."""

    CHEMIN = "Shared/Japon 2025/David/20250602_140944.heic"

    def test_extraction_sur_une_vraie_photo_animee(self):
        from voyages.nextcloud import client_depuis_settings

        octets = client_depuis_settings().telecharger(self.CHEMIN)
        position = video_embarquee(octets)

        self.assertIsNotNone(position)
        clip = octets[position]
        self.assertEqual(len(clip), 4_500_927)
        self.assertEqual(clip[4:8], b"ftyp")
        sonde = sonde_de(clip)
        codecs = {f["codec_type"]: f["codec_name"] for f in sonde["streams"]}
        self.assertEqual(codecs["video"], "hevc")
        infos = infos_video(sonde)
        self.assertAlmostEqual(infos.duree, 3.14, delta=0.05)
        # Tenue verticalement : 984×1312 une fois la rotation appliquée.
        self.assertEqual((infos.largeur, infos.hauteur), (984, 1312))


# --- Métadonnées d'une vidéo (sorties ffprobe de vrais fichiers, positions modifiées) ---

SAMSUNG = {
    "streams": [
        {"codec_type": "video", "codec_name": "hevc", "width": 1920, "height": 1080,
         "avg_frame_rate": "59971/1000", "r_frame_rate": "60/1", "color_transfer": "smpte2084",
         "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}]},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
    "format": {"duration": "54.120000", "tags": {
        "creation_time": "2025-06-01T05:27:09.000000Z", "location": "+35.6000+139.7000/",
        "location-eng": "+35.6000+139.7000/", "com.samsung.android.utc_offset": "+0900",
    }},
}
IPHONE = {
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 3840, "height": 2160, "avg_frame_rate": "25/1",
         "side_data_list": [{"rotation": -90}]},
        {"codec_type": "audio", "codec_name": "aac"},
        {"codec_type": "data", "tags": {"handler_name": "Core Media Metadata"}},
    ],
    "format": {"duration": "10.800000", "tags": {
        "creation_time": "2025-06-05T01:03:47.000000Z",
        "com.apple.quicktime.location.ISO6709": "+35.0100+135.6700+161.226/",
        "com.apple.quicktime.make": "Apple", "com.apple.quicktime.model": "iPhone 14 Pro Max",
        "com.apple.quicktime.creationdate": "2025-06-05T10:03:47+0900",
    }},
}
WHATSAPP = {
    "streams": [{"codec_type": "video", "width": 848, "height": 480, "avg_frame_rate": "29773/1000"}],
    "format": {"duration": "4.440000", "tags": {"creation_time": "0000-00-00T00:00:00.000000Z"}},
}
EXPORT_HUGO = {  # date interne = date d'export (12 juin), la bonne est dans le nom
    "streams": [{"codec_type": "audio"}, {"codec_type": "video", "width": 1280, "height": 720, "avg_frame_rate": "25/1"}],
    "format": {"duration": "10.28", "tags": {
        "creation_time": "2025-06-12T04:10:44.000000Z", "location": "+35.2500+139.1500+13.987000/",
    }},
}


class MetadonneesVideoTests(SimpleTestCase):
    def test_samsung(self):
        meta = metadonnees_video(SAMSUNG, TOKYO)
        self.assertEqual(meta.prise_le, datetime(2025, 6, 1, 5, 27, 9, tzinfo=timezone.utc))
        self.assertEqual((meta.latitude, meta.longitude, meta.altitude), (35.6, 139.7, None))
        self.assertEqual(meta.duree, 54.12)
        self.assertEqual(meta.appareil, "")
        infos = infos_video(SAMSUNG)
        self.assertEqual((infos.largeur, infos.hauteur, infos.hdr, infos.a_son), (1080, 1920, True, True))
        self.assertAlmostEqual(infos.ips, 59.97, places=2)

    def test_iphone_date_avec_decalage_et_altitude(self):
        meta = metadonnees_video(IPHONE, TOKYO)
        self.assertEqual(meta.prise_le, datetime(2025, 6, 5, 1, 3, 47, tzinfo=timezone.utc))
        self.assertEqual((meta.latitude, meta.longitude, meta.altitude), (35.01, 135.67, 161.23))
        self.assertEqual(meta.appareil, "Apple iPhone 14 Pro Max")  # comme ses photos
        self.assertEqual((infos_video(IPHONE).largeur, infos_video(IPHONE).hauteur), (2160, 3840))

    def test_whatsapp_sans_date_ni_position(self):
        meta = metadonnees_video(WHATSAPP, TOKYO)
        self.assertIsNone(meta.prise_le)
        self.assertIsNone(meta.latitude)
        self.assertEqual(meta.duree, 4.44)

    def test_date_du_nom_seulement_avec_l_horloge_nom_de_fichier(self):
        nom = "Shared/Japon 2025/Hugo/25-06-03 08-20-53 3981.mov"
        sans = metadonnees_video(EXPORT_HUGO, TOKYO, {}, nom)
        self.assertEqual(sans.prise_le.date(), date(2025, 6, 12))
        avec = metadonnees_video(EXPORT_HUGO, TOKYO, {"nom de fichier": PARIS}, nom)
        # 08:20:53 à Paris (UTC+2) = 06:20:53 UTC = 15:20 à Tokyo.
        self.assertEqual(avec.prise_le, datetime(2025, 6, 3, 6, 20, 53, tzinfo=timezone.utc))
        # Un nom sans date garde la date interne, même avec l'horloge.
        autre = metadonnees_video(IPHONE, TOKYO, {"nom de fichier": PARIS}, "Hugo/IMG_4083.MOV")
        self.assertEqual(autre.prise_le, datetime(2025, 6, 5, 1, 3, 47, tzinfo=timezone.utc))

    def test_noms_de_fichier(self):
        self.assertIsNone(date_du_nom("IMG_4083.MOV", PARIS))
        self.assertIsNone(date_du_nom("25-13-03 08-20-53 1.mov", PARIS))  # mois impossible
        self.assertIsNone(date_du_nom("125-06-03 08-20-53.mov", PARIS))
        self.assertEqual(date_du_nom("25-06-03 08-20-53.mov", PARIS).hour, 6)

    def test_valeurs_abimees(self):
        abimee = {"streams": [], "format": {"tags": {"location": "n'importe quoi", "creation_time": "hier"}}}
        meta = metadonnees_video(abimee, TOKYO)
        self.assertEqual((meta.prise_le, meta.latitude, meta.duree), (None, None, None))
        self.assertIsNone(metadonnees_video({"format": {"tags": {"location": "+0.0000+0.0000/"}}}, TOKYO).latitude)

    @skipUnless(FFMPEG, "ffmpeg absent")
    def test_vraie_sonde_ffprobe(self):
        meta = metadonnees_video(sonde_de(video(duree=1)), TOKYO)
        self.assertEqual(meta.prise_le, datetime(2025, 4, 5, 5, 30, tzinfo=timezone.utc))
        self.assertEqual((meta.latitude, meta.longitude), (35.6586, 139.7454))
        self.assertAlmostEqual(meta.duree, 1.0, delta=0.1)


# --- Rendus vidéo ------------------------------------------------------------------

class PlanTaillesTests(SimpleTestCase):
    def test_tailles_sans_agrandir(self):
        self.assertEqual(plan_tailles(1080, 1920), [("video_720", 720, 1280), ("video_1080", 1080, 1920)])
        self.assertEqual(plan_tailles(3840, 2160), [("video_720", 1280, 720), ("video_1080", 1920, 1080)])
        self.assertEqual(plan_tailles(984, 1312), [("video_720", 720, 960), ("video_1080", 984, 1312)])
        self.assertEqual(plan_tailles(480, 848), [("video_720", 480, 848)])
        self.assertEqual(plan_tailles(720, 1280), [("video_720", 720, 1280)])

    def test_dimensions_paires(self):
        for taille, largeur, hauteur in plan_tailles(1001, 1335):
            self.assertEqual((largeur % 2, hauteur % 2), (0, 0), taille)


def flux(chemin) -> list[dict]:
    sortie = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(chemin)],
        capture_output=True, check=True,
    ).stdout
    return json.loads(sortie)


def flux_sonde(octets) -> dict:
    """Première piste vidéo d'une source en mémoire, avec ses données annexes (premières images)."""
    with entree_memoire(octets) as entree:
        sortie = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals", "%+#1",
             "-show_entries", "frame_side_data=side_data_type:stream_side_data=side_data_type", "-print_format", "json", *entree.args[1:]],
            capture_output=True, check=True, pass_fds=entree.pass_fds,
        ).stdout
    donnees = json.loads(sortie)
    annexes = [d for f in donnees.get("frames", []) for d in f.get("side_data_list", [])]
    annexes += [d for s in donnees.get("streams", []) for d in s.get("side_data_list", [])]
    return {"side_data_list": annexes}


@skipUnless(FFMPEG, "ffmpeg absent")
class ProduireVideosTests(CacheTemporaire, SimpleTestCase):
    def produire(self, octets, son=True):
        with entree_memoire(octets) as entree:
            return produire_videos(entree, self.cache, "rendus/1/test", son=son)

    @skipUnless(EXIFTOOL, "exiftool absent")
    def test_video_sans_gps_apres_rendu(self):
        source = video(duree=1, taille=(640, 480), location="+35.6586+139.7454/")
        # La source porte bien une position, visible par exiftool.
        with entree_memoire(source) as entree:
            sortie = subprocess.run([EXIFTOOL, "-gps:all", "-userdata:all", entree.args[-1]],
                                    capture_output=True, text=True, pass_fds=entree.pass_fds).stdout
        self.assertIn("35", sortie)

        resultat = self.produire(source)

        for fichier in resultat.fichiers:
            chemin = self.cache / fichier.fichier
            sortie = subprocess.run(
                [EXIFTOOL, "-a", "-s", "-gps:all", "-userdata:all", "-keys:all", "-xmp:all", str(chemin)],
                capture_output=True, text=True, check=False,
            ).stdout
            self.assertEqual(sortie.strip(), "", fichier.taille)
            octets = chemin.read_bytes()
            self.assertNotIn(b"+35.6586", octets)
            self.assertNotIn(b"\xa9xyz", octets)
            sonde = flux(chemin)
            self.assertNotIn("location", sonde["format"].get("tags", {}))
            self.assertNotIn("creation_time", sonde["format"].get("tags", {}))

    def test_seules_l_image_et_le_son_sont_gardes(self):
        resultat = self.produire(video(duree=1, taille=(640, 480)))
        sonde = flux(self.cache / resultat.fichiers[0].fichier)
        self.assertEqual(sorted(f["codec_type"] for f in sonde["streams"]), ["audio", "video"])
        image_ = next(f for f in sonde["streams"] if f["codec_type"] == "video")
        self.assertEqual((image_["codec_name"], image_["pix_fmt"], image_["profile"]), ("h264", "yuv420p", "High"))

    def test_photo_animee_sans_son(self):
        resultat = self.produire(video(duree=1, taille=(640, 480)), son=False)
        sonde = flux(self.cache / resultat.fichiers[0].fichier)
        self.assertEqual([f["codec_type"] for f in sonde["streams"]], ["video"])

    def test_rotation_appliquee_aux_pixels_et_tailles(self):
        # 1920×1080 tenue verticalement → rendus 720×1280 et 1080×1920, sans matrice de rotation.
        resultat = self.produire(video(duree=0.5, taille=(1920, 1080), rotation=-90, son=False))
        dimensions = {f.taille: (f.largeur, f.hauteur) for f in resultat.fichiers}
        self.assertEqual(dimensions, {"video_720": (720, 1280), "video_1080": (1080, 1920)})
        for fichier in resultat.fichiers:
            image_ = flux(self.cache / fichier.fichier)["streams"][0]
            self.assertEqual((image_["width"], image_["height"]), (fichier.largeur, fichier.hauteur))
            self.assertFalse([d for d in image_.get("side_data_list", []) if "rotation" in d])
            self.assertEqual(fichier.octets, (self.cache / fichier.fichier).stat().st_size)

    def test_cadence_plafonnee_a_30(self):
        resultat = self.produire(video(duree=1, taille=(320, 240), ips=60, son=False))
        image_ = flux(self.cache / resultat.fichiers[0].fichier)["streams"][0]
        self.assertEqual(image_["avg_frame_rate"], "30/1")

    def test_hdr_converti_en_sdr_sans_ses_metadonnees(self):
        source = video(duree=0.5, taille=(320, 240), son=False, hdr=True)
        # La source porte bien des métadonnées HDR10, comme un Samsung.
        types_source = [d.get("side_data_type") for d in flux_sonde(source)["side_data_list"]]
        self.assertIn("Mastering display metadata", types_source)

        resultat = self.produire(source)

        image_ = flux(self.cache / resultat.fichiers[0].fichier)["streams"][0]
        self.assertEqual((image_["pix_fmt"], image_.get("color_transfer")), ("yuv420p", "bt709"))
        self.assertEqual(image_.get("side_data_list", []), [])

    def test_aucun_fichier_temporaire_ne_reste(self):
        self.produire(video(duree=0.5))
        self.assertEqual([f for f in self.cache.rglob("*.tmp")], [])


# --- Import et génération de bout en bout ------------------------------------------

@skipUnless(FFMPEG, "ffmpeg absent")
class ImportEtRendusMediasTests(CacheTemporaire, TestCase):
    def setUp(self):
        super().setUp()
        self.auteur = get_user_model().objects.create_user("dd")
        self.client_nc = FauxClient({
            "David/20250405_143000.heic": ("e1", photo_animee(date="2025:04:05 14:30:00", decalage="+09:00")),
            "David/20250405_150000.mp4": ("e2", video(duree=1, taille=(640, 360), ips=60, rotation=-90,
                                                         creation_time="2025-04-05T06:00:00.000000Z")),
            "David/20250405_160000.heic": ("e3", image("HEIF", date="2025:04:05 16:00:00", decalage="+09:00")),
        })

    def importer(self, **kwargs):
        kwargs.setdefault("fuseau", "Asia/Tokyo")
        return importer_voyage(self.client_nc, DOSSIER, auteur=self.auteur, **kwargs)

    def generer(self, **kwargs):
        return generer_rendus(fabrique_client=lambda: self.client_nc, processus=1, **kwargs)

    def media(self, nom):
        return Photo.objects.get(chemin_nextcloud=f"{DOSSIER}/David/{nom}")

    def test_types_detectes_a_l_import(self):
        rapport = self.importer()

        self.assertEqual(dict(rapport.types), {"photo": 1, "animee": 1, "video": 1})
        self.assertEqual(rapport.images_nextcloud, 3)
        video_ = self.media("20250405_150000.mp4")
        self.assertEqual(video_.type, Photo.Type.VIDEO)
        self.assertEqual(video_.prise_le, datetime(2025, 4, 5, 6, 0, tzinfo=timezone.utc))
        self.assertEqual(video_.latitude, 35.6586)
        self.assertAlmostEqual(video_.duree, 1.0, delta=0.1)
        self.assertTrue(video_.visible)
        # La vidéo n'est jamais téléchargée : ffprobe la lit en flux.
        self.assertNotIn(video_.chemin_nextcloud, self.client_nc.telechargements)
        self.assertIn(video_.chemin_nextcloud, self.client_nc.sondes)
        self.assertEqual(self.media("20250405_143000.heic").type, Photo.Type.ANIMEE)
        self.assertEqual(self.media("20250405_160000.heic").type, Photo.Type.PHOTO)
        # Insérées dans l'ordre chronologique du jour.
        self.assertEqual(
            [p.chemin_nextcloud.rsplit("/", 1)[1] for p in Photo.objects.order_by("ordre")],
            ["20250405_143000.heic", "20250405_150000.mp4", "20250405_160000.heic"],
        )

    def test_rendus_puis_relance_sans_regeneration(self):
        self.importer()
        rapport = self.generer()
        self.assertEqual((rapport.generees, rapport.erreurs), (3, []))

        animee, video_, photo = (self.media(n) for n in ("20250405_143000.heic", "20250405_150000.mp4", "20250405_160000.heic"))
        tailles = lambda p: sorted(p.rendus.values_list("taille", flat=True))  # noqa: E731
        self.assertEqual(tailles(photo), ["grande", "miniature", "moyenne"])
        # Photo animée 160×120 : une seule taille vidéo (jamais d'agrandissement).
        self.assertEqual(tailles(animee), ["grande", "miniature", "moyenne", "video_720"])
        # Vidéo 640×360 tournée : 360×640, une seule taille vidéo ; poster en WebP.
        self.assertEqual(tailles(video_), ["grande", "miniature", "moyenne", "video_720"])
        self.assertEqual((video_.largeur, video_.hauteur), (360, 640))
        self.assertTrue(video_.couleur.startswith("#") and video_.placeholder)
        self.assertEqual(video_.rendus.get(taille="video_720").format, "mp4")
        self.assertEqual(animee.videos_etag, "e1")

        fichiers = {f: f.stat().st_mtime_ns for f in self.cache.rglob("*") if f.is_file()}
        self.client_nc.telechargements.clear()
        self.client_nc.sondes.clear()

        rapport = self.generer()

        self.assertEqual((rapport.generees, rapport.inchangees), (0, 3))
        self.assertEqual((self.client_nc.telechargements, self.client_nc.sondes), ([], []))
        self.assertEqual({f: f.stat().st_mtime_ns for f in self.cache.rglob("*") if f.is_file()}, fichiers)

    def test_photo_deja_rendue_qui_se_revele_animee_ne_recoit_que_ses_videos(self):
        self.importer()
        animee = self.media("20250405_143000.heic")
        # État d'avant cette étape : photo « fixe », WebP déjà générés.
        Photo.objects.filter(pk=animee.pk).update(type=Photo.Type.PHOTO, version_analyse=0)
        self.generer(photos_ids=[animee.pk])
        webp = {f: f.stat().st_mtime_ns for f in self.cache.rglob("*.webp")}
        self.assertEqual(len(webp), 3)

        rapport = self.importer()  # relit le HEIC une fois (version_analyse)
        self.assertEqual(rapport.reanalysees, 1)
        animee.refresh_from_db()
        self.assertEqual((animee.type, animee.version_analyse), (Photo.Type.ANIMEE, VERSION_ANALYSE))
        rapport = self.generer(photos_ids=[animee.pk])

        self.assertEqual(rapport.generees, 1)
        self.assertEqual({f: f.stat().st_mtime_ns for f in self.cache.rglob("*.webp")}, webp)
        self.assertEqual(len(list(self.cache.rglob("*.mp4"))), 1)

    def test_reanalyse_une_seule_fois(self):
        self.importer()
        Photo.objects.update(version_analyse=0)
        self.client_nc.telechargements.clear()

        self.assertEqual(self.importer().reanalysees, 2)  # les deux HEIC, pas la vidéo
        self.client_nc.telechargements.clear()
        self.client_nc.sondes.clear()
        rapport = self.importer()

        self.assertEqual((rapport.reanalysees, rapport.inchangees), (0, 3))
        self.assertEqual((self.client_nc.telechargements, self.client_nc.sondes), ([], []))

    def test_saisie_de_l_auteur_conservee_a_la_reanalyse(self):
        self.importer()
        Photo.objects.update(version_analyse=0, legende="Shibuya", favori=True)
        self.importer()
        self.assertEqual(set(Photo.objects.values_list("legende", "favori")), {("Shibuya", True)})

    def test_video_sans_date_masquee(self):
        self.client_nc.fichiers["Valérie/VID-20250611-WA0010.mp4"] = (
            "w1", video(duree=0.5, location=None, creation_time=None),
        )
        rapport = self.importer()
        whatsapp = Photo.objects.get(chemin_nextcloud__endswith="WA0010.mp4")
        self.assertFalse(whatsapp.visible)
        self.assertIn(whatsapp.chemin_nextcloud, rapport.sans_date)
        # Rangée à la date du fichier (1er juin), elle n'étire pas les dates du voyage.
        self.assertEqual(whatsapp.jour.date, date(2025, 6, 1))
        voyage = whatsapp.jour.voyage
        self.assertEqual((voyage.date_debut, voyage.date_fin), (date(2025, 4, 5), date(2025, 4, 5)))

    def test_date_par_le_nom_memorisee_et_relue(self):
        nom = "Hugo/25-04-05 08-20-53 3981.mov"
        self.client_nc.fichiers[nom] = ("h1", video(duree=0.5, creation_time="2025-04-12T04:10:44.000000Z"))
        self.importer()
        mov = Photo.objects.get(chemin_nextcloud__endswith="3981.mov")
        self.assertEqual(mov.jour.date, date(2025, 4, 12))

        self.importer(fuseau=None, horloges={"nom de fichier": "Europe/Paris"})

        mov.refresh_from_db()
        self.assertEqual(mov.prise_le, datetime(2025, 4, 5, 6, 20, 53, tzinfo=timezone.utc))
        self.assertEqual(mov.jour.date, date(2025, 4, 5))
        self.assertEqual(mov.jour.voyage.horloges_appareils, {"nom de fichier": "Europe/Paris"})

    def test_video_illisible_signalee_sans_arreter_l_import(self):
        self.client_nc.fichiers["David/abimee.mp4"] = ("x1", b"pas une video")
        rapport = self.importer()
        self.assertEqual([c for c, _ in rapport.erreurs], [f"{DOSSIER}/David/abimee.mp4"])
        self.assertEqual(Photo.objects.count(), 3)

    def test_erreur_de_rendu_ne_fuit_pas_l_authentification(self):
        # Le message d'erreur de ffmpeg ne reprend que sa dernière ligne.
        from voyages.video import VideoErreur, executer

        entree = Entree(args=("-headers", "Authorization: Basic c2VjcmV0\r\n", "-i", "http://127.0.0.1:9/x.mp4"))
        with self.assertRaises(VideoErreur) as erreur:
            executer(["ffprobe", "-v", "error", *entree.args], entree, 30)
        self.assertNotIn("c2VjcmV0", str(erreur.exception))
