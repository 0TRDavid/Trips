from unittest import mock

from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse


class HealthViewTests(TestCase):
    def test_health_ok_quand_la_base_repond(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})

    def test_health_503_quand_la_base_est_injoignable(self):
        with mock.patch(
            "core.views.connection.cursor",
            side_effect=OperationalError("connexion refusée"),
        ):
            response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(), {"status": "error", "database": "connexion refusée"}
        )
