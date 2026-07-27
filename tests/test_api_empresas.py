import unittest

try:
    from fastapi.testclient import TestClient
    from main import app
except ModuleNotFoundError:
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None, "FastAPI no está instalado en el entorno local")
class ApiEmpresasTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_calcular_mensual_acepta_conciliacion_vacacional(self):
        response = self.client.get(
            "/calcular",
            params={
                "rama": "GENERAL",
                "agrup": "GENERAL",
                "categoria": "MAESTRANZA A",
                "mes": "2026-07",
                "vac_goz": 14,
                "adelanto_vacaciones": 250000,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["conciliacion_vacaciones"]["adelanto_aplicado"],
            250000,
        )
        self.assertTrue(
            any(
                item["concepto"] == "Adelanto de vacaciones abonado"
                for item in data["items"]
            )
        )

    def test_calcular_final_informa_indemnizatorio_y_causa(self):
        response = self.client.get(
            "/calcular-final",
            params={
                "rama": "GENERAL",
                "agrup": "GENERAL",
                "categoria": "MAESTRANZA A",
                "fecha_ingreso": "2020-01-01",
                "fecha_egreso": "2026-07-27",
                "tipo": "RENUNCIA",
                "mejor_rem": 1000000,
                "mejor_nr": 120000,
                "sac_devengado_rem": 500000,
                "sac_devengado_nr": 60000,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["tipo"], "RENUNCIA")
        self.assertIn("ind", data["totales"])
        self.assertEqual(
            data["totales"]["neto"],
            round(
                data["totales"]["rem"]
                + data["totales"]["nr"]
                + data["totales"]["ind"]
                - data["totales"]["ded"],
                2,
            ),
        )


if __name__ == "__main__":
    unittest.main()
