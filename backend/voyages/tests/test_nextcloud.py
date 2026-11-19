from unittest import mock

import requests
from django.test import SimpleTestCase

from voyages.nextcloud import ClientWebDAV, NextcloudErreur, analyser_propfind

PREFIXE = "/remote.php/dav/files/carnet/"


def reponse_dav(href, *, dossier=False, etag="abc", taille=1000, statut="HTTP/1.1 200 OK"):
    type_ = "<d:resourcetype><d:collection/></d:resourcetype>" if dossier else "<d:resourcetype/>"
    autres = "" if dossier else (
        f'<d:getetag>"{etag}"</d:getetag>'
        f"<d:getcontentlength>{taille}</d:getcontentlength>"
    )
    return f"""<d:response><d:href>{href}</d:href><d:propstat><d:prop>{type_}{autres}
      <d:getlastmodified>Sat, 05 Apr 2025 10:00:00 GMT</d:getlastmodified>
    </d:prop><d:status>{statut}</d:status></d:propstat></d:response>"""


def multistatus(*reponses):
    return ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:">' + "".join(reponses) + "</d:multistatus>").encode()


class AnalysePropfindTests(SimpleTestCase):
    def test_chemins_decodes_etag_nettoye_dossiers_marques(self):
        xml = multistatus(
            reponse_dav(PREFIXE + "Shared/Japon%202025%281%29/", dossier=True),
            reponse_dav(PREFIXE + "Shared/Japon%202025%281%29/Kyoto%20%C3%A9t%C3%A9/", dossier=True),
            reponse_dav(PREFIXE + "Shared/Japon%202025%281%29/IMG_0001.HEIC", etag="e1"),
        )
        elements = analyser_propfind(xml, PREFIXE)

        self.assertEqual(
            [e.chemin for e in elements],
            ["Shared/Japon 2025(1)", "Shared/Japon 2025(1)/Kyoto été", "Shared/Japon 2025(1)/IMG_0001.HEIC"],
        )
        self.assertEqual([e.est_dossier for e in elements], [True, True, False])
        photo = elements[2]
        self.assertEqual(photo.etag, "e1")
        self.assertEqual(photo.taille, 1000)
        self.assertEqual(photo.modifie_le.year, 2025)

    def test_filtre_des_extensions_sans_tenir_compte_de_la_casse(self):
        xml = multistatus(*[
            reponse_dav(PREFIXE + f"V/{nom}")
            for nom in ["a.HEIC", "b.heif", "c.jpg", "d.JPEG", "e.MOV", "f.AAE", "g.png", "h.CR2", "sans_extension"]
        ])
        elements = analyser_propfind(xml, PREFIXE)

        self.assertEqual(
            [e.chemin for e in elements if e.est_image],
            ["V/a.HEIC", "V/b.heif", "V/c.jpg", "V/d.JPEG", "V/h.CR2"],
        )

    def test_propriete_en_erreur_ignoree(self):
        xml = multistatus(reponse_dav(PREFIXE + "V/a.jpg", statut="HTTP/1.1 404 Not Found"))
        self.assertEqual(analyser_propfind(xml, PREFIXE), [])


class ClientTests(SimpleTestCase):
    def setUp(self):
        self.client_dav = ClientWebDAV("https://cloud.exemple/", "carnet", "secret-tres-prive")

    def test_url_encodee(self):
        self.assertEqual(
            self.client_dav.url("/Shared/Japon 2025-20260610_112052(1)/"),
            "https://cloud.exemple/remote.php/dav/files/carnet/Shared/Japon%202025-20260610_112052%281%29",
        )

    def test_parcours_recursif_des_sous_dossiers(self):
        reponses = {
            "Shared/V": multistatus(
                reponse_dav(PREFIXE + "Shared/V/", dossier=True),
                reponse_dav(PREFIXE + "Shared/V/a.jpg"),
                reponse_dav(PREFIXE + "Shared/V/Jour%202/", dossier=True),
            ),
            "Shared/V/Jour 2": multistatus(
                reponse_dav(PREFIXE + "Shared/V/Jour%202/", dossier=True),
                reponse_dav(PREFIXE + "Shared/V/Jour%202/b.heic"),
            ),
        }
        appels = []

        def faux_requete(methode, chemin, url=None, **kwargs):
            appels.append(chemin)
            return mock.Mock(content=reponses[chemin], status_code=207)

        with mock.patch.object(self.client_dav, "_requete", side_effect=faux_requete):
            fichiers = self.client_dav.lister("/Shared/V/")

        self.assertEqual([f.chemin for f in fichiers], ["Shared/V/Jour 2/b.heic", "Shared/V/a.jpg"])
        self.assertEqual(sorted(appels), ["Shared/V", "Shared/V/Jour 2"])

    def test_telechargement_partiel_demande_une_plage(self):
        with mock.patch.object(
            self.client_dav.session, "request", return_value=mock.Mock(status_code=206, content=b"x")
        ) as requete:
            self.client_dav.telecharger("V/a.CR2", limite=1024)
            self.client_dav.telecharger("V/b.jpg")

        self.assertEqual(requete.call_args_list[0].kwargs["headers"], {"Range": "bytes=0-1023"})
        self.assertEqual(requete.call_args_list[1].kwargs["headers"], {})

    def verifier_erreur(self, statut, attendu):
        with mock.patch.object(
            self.client_dav.session, "request", return_value=mock.Mock(status_code=statut)
        ):
            with self.assertRaises(NextcloudErreur) as ctx:
                self.client_dav.lister("Shared/V")
        self.assertIn(attendu, str(ctx.exception))
        self.assertNotIn("secret-tres-prive", str(ctx.exception))

    def test_erreur_401_lisible_sans_mot_de_passe(self):
        self.verifier_erreur(401, "authentification")

    def test_erreur_404_lisible(self):
        self.verifier_erreur(404, "Shared/V")

    def test_reseau_injoignable(self):
        with mock.patch.object(
            self.client_dav.session, "request", side_effect=requests.ConnectionError("boum https://carnet:secret-tres-prive@x")
        ):
            with self.assertRaises(NextcloudErreur) as ctx:
                self.client_dav.telecharger("Shared/V/a.jpg")
        self.assertNotIn("secret-tres-prive", str(ctx.exception))

    def test_identifiants_manquants(self):
        with self.assertRaises(NextcloudErreur):
            ClientWebDAV("", "carnet", "x")
