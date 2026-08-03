import unittest

import escalas


class FunebresAcuerdoJulio2026Test(unittest.TestCase):
    MONTHS = [
        "2026-07", "2026-08", "2026-09", "2026-10", "2026-11",
        "2026-12", "2027-01", "2027-02", "2027-03", "2027-04", "2027-05",
    ]

    BASICS = {
        "MAESTRANZA – PEÓN (A)": [1137046, 1160484, 1183923, 1183923, 1183923, 1203923, 1223923, 1243923, 1263923, 1283923, 1303923],
        "MAESTRANZA – AYUDANTE – CAMILLERO – SERENO (B)": [1140577, 1164082, 1187586, 1187586, 1187586, 1207586, 1227586, 1247586, 1267586, 1287586, 1307586],
        "MAESTRANZA – PORTERO (C)": [1151206, 1174908, 1198611, 1198611, 1198611, 1218611, 1238611, 1258611, 1278611, 1298611, 1318611],
        "AUXILIAR – PERSONAL SALAS VELATORIAS (A)": [1152373, 1176098, 1199822, 1199822, 1199822, 1219822, 1239822, 1259822, 1279822, 1299822, 1319822],
        "ADMINISTRATIVO (D)": [1172372, 1196469, 1220567, 1220567, 1220567, 1240567, 1260567, 1280567, 1300567, 1320567, 1340567],
        "AUXILIAR – CAPILLERO – SOLDADOR – LUSTRADOR – SASTRE (B)": [1160330, 1184202, 1208075, 1208075, 1208075, 1228075, 1248075, 1268075, 1288075, 1308075, 1328075],
        "AUXILIAR – CHOFER – FURGONERO – AMBULANCIERO (B)": [1160330, 1184202, 1208075, 1208075, 1208075, 1228075, 1248075, 1268075, 1288075, 1308075, 1328075],
    }

    ADDITIONALS = {
        "Manipulación de cadáveres": [64645, 65851, 67056, 67056, 67056, 68189, 69322, 70454, 71587, 72720, 73853],
        "Resto del personal": [30248, 30812, 31376, 31376, 31376, 31906, 32436, 32966, 33496, 34026, 34556],
        "Chofer/Furgonero": [21955, 22365, 22774, 22774, 22774, 23159, 23544, 23928, 24313, 24698, 25082],
        "Indumentaria": [11362, 11574, 11786, 11786, 11786, 11985, 12184, 12383, 12582, 12781, 12980],
    }

    def test_basicos_y_asignaciones_coinciden_con_escala(self):
        totals = [120000, 120000, 120000, 120000, 120000, 100000, 80000, 60000, 40000, 20000, 0]
        extras = [25000, 25000, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        for category, basics in self.BASICS.items():
            for index, month in enumerate(self.MONTHS):
                with self.subTest(category=category, month=month):
                    row = escalas.get_payload("FÚNEBRES", month, "—", category)
                    self.assertTrue(row["ok"])
                    self.assertEqual(row["basico"], basics[index])
                    self.assertEqual(row["no_rem"] + row["suma_fija"], totals[index])
                    self.assertEqual(row["extraordinaria"], extras[index])

    def test_adicionales_coinciden_mes_por_mes(self):
        for index, month in enumerate(self.MONTHS):
            rows = {row["label"]: row["monto"] for row in escalas.get_adicionales_funebres(month)}
            self.assertEqual(set(rows), set(self.ADDITIONALS))
            for label, values in self.ADDITIONALS.items():
                with self.subTest(label=label, month=month):
                    self.assertEqual(rows[label], values[index])

    def test_asignacion_extraordinaria_no_integra_adicionales(self):
        defs = escalas.get_adicionales_funebres("2026-08")
        result = escalas.calcular_payload(
            rama="FÚNEBRES",
            mes="2026-08",
            agrup="—",
            categoria="ADMINISTRATIVO (D)",
            jornada=48,
            fun_adic=";".join(row["id"] for row in defs),
        )
        items = {item["concepto"]: item for item in result["items"]}
        self.assertEqual(items["Manipulación de cadáveres"]["r"], 65851)
        self.assertEqual(items["Resto del personal"]["r"], 30812)
        self.assertEqual(items["Chofer/Furgonero"]["r"], 22365)
        self.assertEqual(items["Indumentaria"]["r"], 11574)
        self.assertEqual(items["Asignación Extraordinaria por Única Vez - Revisión 2026"]["n"], 25000)


if __name__ == "__main__":
    unittest.main()
