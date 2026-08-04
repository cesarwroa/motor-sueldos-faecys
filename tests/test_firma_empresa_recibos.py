from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FirmaEmpresaRecibosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "public" / "empresas.html").read_text(encoding="utf-8")

    def test_empresa_puede_cargar_y_activar_firma(self):
        self.assertIn('id="companySignatureFile"', self.source)
        self.assertIn('id="companySignaturePreview"', self.source)
        self.assertIn('id="companySignatureEnabled"', self.source)
        self.assertIn("signature_image:companySignatureImage", self.source)
        self.assertIn("signature_enabled:!!companySignatureImage", self.source)

    def test_recibo_inserta_solo_la_firma_activada(self):
        self.assertIn("settings.signature_enabled&&settings.signature_image", self.source)
        self.assertIn('class="receipt-employer-signature"', self.source)
        self.assertIn('class="receipt-signature-image-slot">${signature}', self.source)
        self.assertIn("max-width:44mm;max-height:12mm;object-fit:contain", self.source)


if __name__ == "__main__":
    unittest.main()
