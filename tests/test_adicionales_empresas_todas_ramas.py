import unittest

import escalas


def item_starting(result, prefix):
    return next((item for item in result["items"] if item["concepto"].startswith(prefix)), None)


class AdicionalesEmpresasTodasRamasTest(unittest.TestCase):
    def test_general_caja_faltante_vidriera_km_y_zona(self):
        result = escalas.calcular_payload(
            rama="GENERAL", agrup="GENERAL", categoria="MAESTRANZA A", mes="2026-07",
            jornada=48, manejo_caja=True, cajero_tipo="A", faltante_caja=999999,
            armado_vidriera=True, km_tipo="CH", km_menos100=10, km_mas100=5,
            zona_pct=10, a_cuenta_rem=1234,
        )
        caja = item_starting(result, "Manejo de Caja")
        faltante = item_starting(result, "Faltante de caja")
        self.assertGreater(caja["n"], 0)
        self.assertEqual(faltante["d"], caja["n"])
        self.assertGreater(item_starting(result, "Armado de vidriera")["r"], 0)
        self.assertGreater(item_starting(result, "Adicional por KM")["r"], 0)
        self.assertGreater(item_starting(result, "Zona desfavorable")["r"], 0)
        self.assertEqual(item_starting(result, "A cuenta futuros")["r"], 1234)

    def test_cereales_usa_referencia_del_mismo_agrupamiento(self):
        agrup = "HASTA 25.000 Tn."
        reference = escalas.get_payload("CEREALES", "2026-06", agrup, "VENDEDORES B")
        result = escalas.calcular_payload(
            rama="CEREALES", agrup=agrup, categoria="MAESTRANZA A", mes="2026-06",
            jornada=48, armado_vidriera=True, manejo_caja=True, cajero_tipo="B",
        )
        vidriera = item_starting(result, "Armado de vidriera")
        self.assertEqual(vidriera["base"], reference["basico"])
        self.assertGreater(item_starting(result, "Manejo de Caja")["n"], 0)

    def test_turismo_titulo_y_km_c4_c5(self):
        for category, km_type in [("C4 - GUIA / CONDUCTOR", "C4"), ("C5 - ENCARGADO DE VEHICULO", "C5")]:
            with self.subTest(category=category):
                result = escalas.calcular_payload(
                    rama="TURISMO", agrup="OPERATIVO", categoria=category, mes="2026-08",
                    jornada=48, titulo_pct=2.5, km_tipo=km_type, km_menos100=10, km_mas100=5,
                )
                self.assertGreater(item_starting(result, "Adicional por KM (Turismo")["r"], 0)
                self.assertGreater(item_starting(result, "Adicional por Título")["r"], 0)

    def test_agua_y_call_center_admiten_sus_variables(self):
        agua = escalas.calcular_payload(
            rama="AGUA POTABLE", agrup="MAESTRANZA", categoria="MAESTRANZA C",
            mes="2026-07", jornada=48, conexiones=600,
        )
        self.assertEqual(agua["basico_base"], 1_232_373.57)
        self.assertEqual(agua["no_rem_base"] + agua["suma_fija_base"], 128_400)
        call = escalas.calcular_payload(
            rama="CALL CENTER", agrup="CALL CENTER", categoria="CATEGORIA 3: OPERACION A 20HS",
            mes="2026-07", jornada=20, zona_pct=10,
        )
        self.assertGreater(item_starting(call, "Zona desfavorable")["r"], 0)


if __name__ == "__main__":
    unittest.main()
