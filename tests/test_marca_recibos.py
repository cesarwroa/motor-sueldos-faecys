from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MarcaRecibosTest(unittest.TestCase):
    def test_recibos_empresa_no_llevan_marca(self):
        html = (ROOT / "public" / "empresas.html").read_text(encoding="utf-8")
        self.assertNotIn('<div class="anexo-brand-footer">Calculadora de Comercio</div>', html)

    def test_recibos_calculadora_conservan_marca(self):
        html = (ROOT / "public" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="anexo-brand-footer">Calculadora de Comercio</div>', html)


if __name__ == "__main__":
    unittest.main()
