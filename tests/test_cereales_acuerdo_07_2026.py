import unittest

import escalas


class CerealesAcuerdoJulio2026Test(unittest.TestCase):
    def test_escalas_oficiales_tres_meses_y_tres_tonelajes(self):
        expected = {
            ("2026-07", "HASTA 25.000 Tn."): (1_273_869, 25_000),
            ("2026-07", "DESDE 25.001 A 75.000 Tn."): (1_288_246, 25_000),
            ("2026-07", "MAS DE 75.000 Tn."): (1_306_693, 25_000),
            ("2026-08", "HASTA 25.000 Tn."): (1_299_858, 25_000),
            ("2026-08", "DESDE 25.001 A 75.000 Tn."): (1_314_504, 25_000),
            ("2026-08", "MAS DE 75.000 Tn."): (1_333_294, 25_000),
            ("2026-09", "HASTA 25.000 Tn."): (1_325_848, 0),
            ("2026-09", "DESDE 25.001 A 75.000 Tn."): (1_340_761, 0),
            ("2026-09", "MAS DE 75.000 Tn."): (1_359_896, 0),
        }
        for (month, group), (basic, extra) in expected.items():
            with self.subTest(month=month, group=group):
                payload = escalas.get_payload("CEREALES", month, group, "MAESTRANZA A")
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["basico"], basic)
                self.assertEqual(payload["no_rem"], 0)
                self.assertEqual(payload["suma_fija"], 120_000)
                self.assertEqual(payload["extraordinaria"], extra)

    def test_menores_seis_horas_conservan_importes_oficiales(self):
        payload = escalas.get_payload(
            "CEREALES", "2026-07", "HASTA 25.000 Tn.", "6 HS - MENOR - - 16 AÑOS"
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["basico"], 1_199_809)
        self.assertEqual(payload["no_rem"], 0)
        self.assertEqual(payload["suma_fija"], 90_000)
        self.assertEqual(payload["extraordinaria"], 25_000)

    def test_extraordinaria_no_genera_antiguedad_presentismo_ni_aportes(self):
        data = escalas.calcular_payload(
            rama="CEREALES",
            agrup="HASTA 25.000 Tn.",
            categoria="MAESTRANZA A",
            mes="2026-07",
            jornada=48,
            anios_antig=10,
            afiliado=True,
            sind_pct=2,
            osecac=True,
        )
        concepts = {item["concepto"]: item for item in data["items"]}
        extraordinary = next(
            item for label, item in concepts.items() if label.lower().startswith("asignación extraordinaria")
        )
        self.assertEqual(extraordinary["n"], 25_000)
        self.assertEqual(concepts["Antigüedad (NR)"]["base"], 120_000)
        self.assertEqual(concepts["Presentismo (NR)"]["base"], 120_000)

        base_without_extra = (
            data["totales"]["rem"]
            + concepts["Recomp. Acu. Abr 26"]["n"]
            + concepts["Antigüedad (NR)"]["n"]
            + concepts["Presentismo (NR)"]["n"]
        )
        obra_social = next(
            item
            for item in data["contribuciones_empleador"]["items"]
            if item["concepto"] == "Obra Social empleador (6%)"
        )
        self.assertAlmostEqual(obra_social["base"], base_without_extra, places=2)
        self.assertNotEqual(obra_social["base"], base_without_extra + 25_000)


if __name__ == "__main__":
    unittest.main()
