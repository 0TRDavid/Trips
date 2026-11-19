"""Tracé GPS allégé : simplification, ordre, arrondi, frontières entre jours."""

from datetime import date

from django.test import SimpleTestCase

from voyages.trace import construire_trace, simplifier

J1, J2 = date(2025, 6, 1), date(2025, 6, 2)


class SimplifierTests(SimpleTestCase):
    def test_points_alignes_reduits_aux_extremites(self):
        ligne = [(35.0, 139.0 + i * 0.001) for i in range(20)]  # ~90 m entre deux points, tout droit

        self.assertEqual(simplifier(ligne), [0, 19])

    def test_virage_conserve(self):
        # Un « L » : aller vers l'est, puis vers le nord (≈ 1 km chacun).
        points = [(35.0, 139.0 + i * 0.001) for i in range(11)] + [(35.0 + i * 0.001, 139.01) for i in range(1, 11)]

        self.assertEqual(simplifier(points), [0, 10, 20])

    def test_petits_ecarts_sous_la_tolerance_retires(self):
        points = [(35.0, 139.0), (35.0001, 139.005), (35.0, 139.01)]  # écart ≈ 11 m < 30 m

        self.assertEqual(simplifier(points), [0, 2])

    def test_deux_points_ou_moins(self):
        self.assertEqual(simplifier([]), [])
        self.assertEqual(simplifier([(35.0, 139.0)]), [0])


class ConstruireTraceTests(SimpleTestCase):
    def test_frontieres_entre_jours_conservees_et_ordre_respecte(self):
        positions = [(J1, 35.0, 139.0 + i * 0.001) for i in range(10)] + [
            (J2, 35.0, 139.009 + i * 0.001) for i in range(10)
        ]

        trace = construire_trace(positions)

        self.assertEqual([p["jour"] for p in trace], ["2025-06-01"] * 2 + ["2025-06-02"] * 2)
        self.assertEqual([p["lon"] for p in trace], [139.0, 139.009, 139.009, 139.018])

    def test_arrondi_a_cinq_decimales(self):
        trace = construire_trace([(J1, 35.123456789, 139.987654321)])

        self.assertEqual(trace, [{"lat": 35.12346, "lon": 139.98765, "jour": "2025-06-01"}])

    def test_vide(self):
        self.assertEqual(construire_trace([]), [])
