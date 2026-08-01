import unittest

import escalas


class AguaPotableAcuerdoJulio2026Test(unittest.TestCase):
    def test_maestranza_aplica_aumento_y_postergacion(self):
        expected = {
            "2026-07": (1_151_751, 100_000, 20_000, 25_000),
            "2026-08": (1_175_464, 100_000, 20_000, 25_000),
            "2026-09": (1_199_177, 100_000, 20_000, 0),
            "2026-12": (1_219_177, 80_000, 20_000, 0),
            "2027-04": (1_299_177, 0, 20_000, 0),
            "2027-05": (1_319_177, 0, 0, 0),
        }
        for month, values in expected.items():
            with self.subTest(month=month):
                row = escalas.get_payload(
                    "AGUA POTABLE",
                    month,
                    "MAESTRANZA",
                    "Maestranza C",
                )
                self.assertTrue(row["ok"])
                self.assertEqual(
                    (
                        row["basico"],
                        row["no_rem"],
                        row["suma_fija"],
                        row["extraordinaria"],
                    ),
                    values,
                )

    def test_extraordinaria_es_proporcional_por_categoria(self):
        cases = [
            (
                "PERSONAL SUPERVISIÓN y JEFATURA",
                "OPERADOR DE 1ra.",
                75_000,
            ),
            ("PERSONAL TÉCNICO", "OPERADOR DE 2da.", 41_250),
            ("PERSONAL TÉCNICO", "OPERADOR DE 1ra.", 47_500),
            (
                "PERSONAL AUXILIAR / ADMINISTRATIVO",
                "AYUDANTE",
                27_500,
            ),
            (
                "PERSONAL AUXILIAR / ADMINISTRATIVO",
                "MEDIO OFICIAL / ADMINISTRATIVO 2da.",
                33_750,
            ),
            (
                "PERSONAL AUXILIAR / ADMINISTRATIVO",
                "OFICIAL / ADMINISTRATIVO 1ra.",
                37_500,
            ),
            (
                "PERSONAL AUXILIAR / ADMINISTRATIVO",
                "OFICIAL ENCARGADO / ENCARGADO",
                42_500,
            ),
            ("MAESTRANZA", "Maestranza C", 25_000),
        ]
        for grouping, category, expected in cases:
            with self.subTest(category=category):
                row = escalas.get_payload(
                    "AGUA POTABLE",
                    "2026-07",
                    grouping,
                    category,
                )
                self.assertEqual(row["extraordinaria"], expected)

    def test_conexiones_escalan_tambien_la_extraordinaria(self):
        row = escalas.get_payload(
            "AGUA POTABLE",
            "2026-07",
            "MAESTRANZA",
            "Maestranza C",
            conex_cat="B",
        )
        self.assertEqual(row["basico"], 1_232_373.57)
        self.assertEqual(row["no_rem"], 107_000)
        self.assertEqual(row["suma_fija"], 21_400)
        self.assertEqual(row["extraordinaria"], 26_750)


if __name__ == "__main__":
    unittest.main()
