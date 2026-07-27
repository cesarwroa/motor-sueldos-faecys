import unittest

from escalas import calcular_payload


class SacEmpresasTest(unittest.TestCase):
    def calcular(self, factor=1):
        return calcular_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="MAESTRANZA A",
            mes="2026-06",
            jornada=48,
            sac_base_rem=1_200_000,
            sac_base_nr=200_000,
            sac_factor=factor,
            sac_base_period="2026-05",
        )

    def test_usa_la_mejor_liquidacion_guardada(self):
        sac = self.calcular()["recibo_sac"]
        self.assertEqual(sac["totales"]["rem"], 600_000)
        self.assertEqual(sac["totales"]["nr"], 100_000)
        self.assertEqual(sac["base_sac"]["origen"], "liquidaciones_guardadas")
        self.assertEqual(sac["base_sac"]["periodo"], "2026-05")
        self.assertEqual(sac["base_sac"]["total"], 1_400_000)

    def test_aplica_proporcionalidad_sobre_la_base_historica(self):
        sac = self.calcular(factor=0.5)["recibo_sac"]
        self.assertEqual(sac["totales"]["rem"], 300_000)
        self.assertEqual(sac["totales"]["nr"], 50_000)
        self.assertEqual(sac["base_sac"]["factor"], 0.5)

    def test_informa_contribuciones_propias_del_sac(self):
        sac = self.calcular()["recibo_sac"]
        self.assertGreater(sac["totales"]["contribuciones_empleador"], 0)
        self.assertGreater(sac["totales"]["costo_laboral_total"], 700_000)


if __name__ == "__main__":
    unittest.main()
