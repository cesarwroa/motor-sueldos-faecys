import unittest
from pathlib import Path


class ContratoEmpresaAdicionalesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.html = (root / "public" / "empresas.html").read_text(encoding="utf-8")

    def test_portal_expone_todos_los_adicionales_especificos(self):
        required = [
            "water_connections", "funeral_general", "funeral_other", "funeral_driver",
            "funeral_clothing", "tourism_title_tertiary", "tourism_title_degree",
            "tourism_km_c4_under100", "tourism_km_c4_over100",
            "tourism_km_c5_under100", "tourism_km_c5_over100",
            "km_driver_under100", "km_driver_over100", "km_helper_under100",
            "km_helper_over100", "cash_handling_a", "cash_handling_b", "cash_handling_c",
            "cash_shortage", "window_dressing", "zone_percentage", "commission",
            "viaticos_nr", "bonus", "other",
        ]
        for concept in required:
            with self.subTest(concept=concept):
                self.assertIn(f'value="{concept}"', self.html)

    def test_portal_valida_adicionales_por_rama(self):
        self.assertIn('["GENERAL","CEREALES"]', self.html)
        self.assertIn('type.startsWith("tourism_km_")', self.html)
        self.assertIn('type.startsWith("funeral_")', self.html)


if __name__ == "__main__":
    unittest.main()
