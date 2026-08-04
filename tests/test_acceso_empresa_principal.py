from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AccesoEmpresaPrincipalTest(unittest.TestCase):
    def test_administrador_acepta_cuenta_de_plataforma(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("def _authenticate_platform_admin", source)
        self.assertIn('session.get("is_platform_admin")', source)
        self.assertIn("valid_platform_admin", source)

    def test_portal_recibe_token_sin_dejarlo_en_la_url(self):
        source = (ROOT / "public" / "empresas.html").read_text(encoding="utf-8")
        self.assertIn("acceptCompanyTokenHandoff", source)
        self.assertIn('params.get("company_token")', source)
        self.assertIn('history.replaceState({},"",location.pathname+location.search)', source)


if __name__ == "__main__":
    unittest.main()
