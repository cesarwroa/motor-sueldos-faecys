import unittest

from escalas import calcular_final_payload, calcular_payload, calcular_vacaciones_payload


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

    def test_jornada_parcial_respeta_la_base_guardada(self):
        sac = calcular_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="MAESTRANZA A",
            mes="2026-12",
            jornada=24,
            sac_base_rem=600_000,
            sac_base_nr=120_000,
            sac_factor=1,
            sac_base_period="2026-11",
        )["recibo_sac"]
        self.assertEqual(sac["totales"]["rem"], 300_000)
        self.assertEqual(sac["totales"]["nr"], 60_000)


class VacacionesEmpresasTest(unittest.TestCase):
    def test_divisor_25_y_deducciones(self):
        result = calcular_vacaciones_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="MAESTRANZA A",
            mes="2026-07",
            dias=14,
            base_rem=1_000_000,
            base_nr=120_000,
        )
        self.assertEqual(result["totales"]["rem"], 560_000)
        self.assertEqual(result["totales"]["nr"], 67_200)
        self.assertEqual(result["base_vacaciones"]["divisor"], 25)
        self.assertGreater(result["totales"]["ded"], 0)
        self.assertGreater(result["totales"]["contribuciones_empleador"], 0)


class LiquidacionFinalEmpresasTest(unittest.TestCase):
    def test_sac_proporcional_usa_devengado_historico(self):
        result = calcular_final_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="MAESTRANZA A",
            fecha_ingreso="2020-01-01",
            fecha_egreso="2026-05-15",
            tipo="RENUNCIA",
            mejor_rem=1_000_000,
            mejor_nr=120_000,
            sac_devengado_rem=4_500_000,
            sac_devengado_nr=540_000,
            vac_no_gozadas_dias=5,
            integracion=False,
        )
        sac_item = next(item for item in result["items"] if item["concepto"] == "SAC proporcional")
        self.assertEqual(sac_item["r"], 375_000)
        self.assertEqual(sac_item["n"], 45_000)
        self.assertEqual(result["base_sac_proporcional"]["origen"], "liquidaciones_guardadas")

    def test_despido_sin_causa_incluye_art_245(self):
        result = calcular_final_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="MAESTRANZA A",
            fecha_ingreso="2020-01-01",
            fecha_egreso="2026-07-15",
            tipo="DESPIDO_SIN_CAUSA",
            mejor_rem=1_000_000,
            mejor_nr=120_000,
            sac_devengado_rem=500_000,
            sac_devengado_nr=60_000,
            preaviso_dias=60,
            integracion=True,
        )
        concepts = [item["concepto"] for item in result["items"]]
        self.assertTrue(any("Art. 245" in concept for concept in concepts))
        self.assertTrue(any("Preaviso" in concept for concept in concepts))
        self.assertTrue(any("Integración mes despido" in concept for concept in concepts))


if __name__ == "__main__":
    unittest.main()
