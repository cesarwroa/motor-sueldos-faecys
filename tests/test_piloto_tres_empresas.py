import unittest

from escalas import calcular_final_payload, calcular_payload, calcular_vacaciones_payload


class PilotoTresEmpresasTest(unittest.TestCase):
    def test_empresa_1_comercio_jornada_completa_con_vacaciones(self):
        vacation = calcular_vacaciones_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="MAESTRANZA A",
            mes="2026-07",
            dias=14,
            base_rem=1_000_000,
            base_nr=120_000,
        )
        monthly = calcular_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="MAESTRANZA A",
            mes="2026-07",
            jornada=48,
            vac_goz=14,
            adelanto_vacaciones=vacation["totales"]["neto"],
        )
        self.assertEqual(
            monthly["conciliacion_vacaciones"]["adelanto_aplicado"],
            vacation["totales"]["neto"],
        )
        self.assertGreater(monthly["totales"]["neto"], 0)

    def test_empresa_2_comercio_jornada_parcial_con_sac_historico(self):
        result = calcular_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="ADMINISTRATIVO A",
            mes="2026-12",
            jornada=24,
            sac_base_rem=600_000,
            sac_base_nr=120_000,
            sac_factor=0.5,
            sac_base_period="2026-11",
        )
        sac = result["recibo_sac"]
        self.assertEqual(sac["totales"]["rem"], 150_000)
        self.assertEqual(sac["totales"]["nr"], 30_000)
        self.assertEqual(sac["base_sac"]["origen"], "liquidaciones_guardadas")

    def test_empresa_3_despido_sin_causa_con_indemnizacion_visible(self):
        result = calcular_final_payload(
            rama="GENERAL",
            agrup="GENERAL",
            categoria="VENDEDOR B",
            fecha_ingreso="2018-02-01",
            fecha_egreso="2026-07-15",
            tipo="DESPIDO_SIN_CAUSA",
            mejor_rem=1_400_000,
            mejor_nr=120_000,
            sac_devengado_rem=7_000_000,
            sac_devengado_nr=600_000,
            preaviso_dias=60,
            integracion=True,
        )
        concepts = [item["concepto"] for item in result["items"]]
        self.assertTrue(any("Art. 245" in concept for concept in concepts))
        self.assertTrue(any("Preaviso" in concept for concept in concepts))
        self.assertGreater(result["totales"]["ind"], 0)
        self.assertEqual(
            result["totales"]["neto"],
            round(
                result["totales"]["rem"]
                + result["totales"]["nr"]
                + result["totales"]["ind"]
                - result["totales"]["ded"],
                2,
            ),
        )


if __name__ == "__main__":
    unittest.main()
