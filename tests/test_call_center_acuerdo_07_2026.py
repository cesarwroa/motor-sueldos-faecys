import unittest

import escalas


class CallCenterAcuerdoJulio2026Test(unittest.TestCase):
    def test_escala_completa_48_horas(self):
        julio = escalas.get_payload(
            "CALL CENTER",
            "2026-07",
            "CALL CENTER",
            "CATEGORIA 1:  MANTENIMIENTO 48hs",
        )
        mayo = escalas.get_payload(
            "CALL CENTER",
            "2027-05",
            "CALL CENTER",
            "CATEGORIA 1:  MANTENIMIENTO 48hs",
        )

        self.assertTrue(julio["ok"])
        self.assertEqual(julio["basico"], 1_151_751)
        self.assertEqual(julio["no_rem"], 120_000)
        self.assertEqual(julio["extraordinaria"], 25_000)
        self.assertTrue(mayo["ok"])
        self.assertEqual(mayo["basico"], 1_319_176)
        self.assertEqual(mayo["no_rem"], 0)
        self.assertEqual(mayo["extraordinaria"], 0)

    def test_jornada_reducida_usa_importes_oficiales_sin_prorrateo_adicional(self):
        data = escalas.calcular_payload(
            rama="CALL CENTER",
            agrup="CALL CENTER",
            categoria="CATEGORIA 3: OPERACION A 20hs",
            mes="2026-07",
            jornada=48,
        )
        conceptos = {item["concepto"]: item for item in data["items"]}

        self.assertTrue(data["ok"])
        self.assertEqual(conceptos["Básico"]["r"], 480_921)
        self.assertEqual(
            conceptos["Aum. NR Suma Fija Acu. Jul 26"]["n"],
            50_000,
        )
        self.assertEqual(
            conceptos[
                "Asignación Extraordinaria por Única Vez - Revisión 2026"
            ]["n"],
            10_417,
        )

    def test_asignacion_extraordinaria_no_genera_derivados_ni_contribuciones(self):
        data = escalas.calcular_payload(
            rama="CALL CENTER",
            agrup="CALL CENTER",
            categoria="CATEGORIA 1:  MANTENIMIENTO 48hs",
            mes="2026-07",
            jornada=48,
            anios_antig=10,
            afiliado=True,
            sind_pct=2,
            osecac=True,
        )
        conceptos = {item["concepto"]: item for item in data["items"]}

        self.assertEqual(conceptos["Antigüedad (NR)"]["base"], 120_000)
        self.assertEqual(conceptos["Presentismo (NR)"]["base"], 120_000)
        self.assertEqual(
            conceptos[
                "Asignación Extraordinaria por Única Vez - Revisión 2026"
            ]["n"],
            25_000,
        )

        base_aportable = (
            data["totales"]["rem"]
            + conceptos["Aum. NR Suma Fija Acu. Jul 26"]["n"]
            + conceptos["Antigüedad (NR)"]["n"]
            + conceptos["Presentismo (NR)"]["n"]
        )
        obra_social = next(
            item
            for item in data["contribuciones_empleador"]["items"]
            if item["concepto"] == "Obra Social empleador (6%)"
        )
        self.assertAlmostEqual(obra_social["base"], base_aportable, places=2)
        self.assertNotEqual(
            obra_social["base"],
            base_aportable + 25_000,
        )


if __name__ == "__main__":
    unittest.main()
