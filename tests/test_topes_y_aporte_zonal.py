import unittest

from escalas import calcular_payload


class TopesYAporteZonalTest(unittest.TestCase):
    def _calcular(self, **overrides):
        params = {
            "rama": "GENERAL",
            "agrup": "GENERAL",
            "categoria": "VENDEDOR B",
            "mes": "2026-07",
            "jornada": 24,
            "anios_antig": 4,
            "fer_no_trab": 1,
        }
        params.update(overrides)
        result = calcular_payload(**params)
        self.assertTrue(result["ok"])
        return result

    def test_tope_limita_jubilacion_e_inssjp_y_su_base_visible(self):
        result = self._calcular(tope_aportes_mensual=600000)
        items = {item["concepto"]: item for item in result["items"]}
        self.assertEqual(items["Jubilación 11%"]["base"], 600000)
        self.assertEqual(items["Jubilación 11%"]["d"], 66000)
        self.assertEqual(items["Ley 19.032 (PAMI) 3%"]["base"], 600000)
        self.assertEqual(items["Ley 19.032 (PAMI) 3%"]["d"], 18000)

    def test_aporte_zonal_es_independiente_de_la_afiliacion(self):
        result = self._calcular(
            afiliado=False,
            aporte_zonal_nombre="Resolución 3/76 - Sindicato Zona Norte",
            aporte_zonal_pct=1,
        )
        item = next(
            row
            for row in result["items"]
            if row["concepto"] == "Resolución 3/76 - Sindicato Zona Norte"
        )
        self.assertEqual(item["unidad"], "1%")
        self.assertEqual(item["d"], round(item["base"] * 0.01, 2))

    def test_afiliacion_admite_porcentaje_y_suma_fija_adicionales(self):
        result = self._calcular(afiliado=True, sind_pct=2, sind_fijo=1500)
        items = {item["concepto"]: item for item in result["items"]}
        percentage = items["Sindicato Afiliación 2%"]
        fixed = items["Sindicato Afiliación"]

        self.assertEqual(percentage["unidad"], "2%")
        self.assertEqual(percentage["d"], round(percentage["base"] * 0.02, 2))
        self.assertEqual(fixed["d"], 1500)


if __name__ == "__main__":
    unittest.main()
