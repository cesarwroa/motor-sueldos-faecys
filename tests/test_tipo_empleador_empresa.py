from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TipoEmpleadorEmpresaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "public" / "empresas.html").read_text(encoding="utf-8-sig")

    def test_tipo_empleador_se_configura_en_la_empresa(self):
        self.assertIn('id="companyArcaEmployerType"', self.source)
        self.assertIn('value="1">1 - MiPyME / inciso B (18%)', self.source)
        self.assertIn('value="4">4 - Servicios o comercio / inciso A (20,40%)', self.source)
        self.assertIn('arca_employer_type:$("companyArcaEmployerType").value', self.source)

    def test_no_se_muestra_como_campo_editable_del_empleado(self):
        self.assertNotIn('label for="employeeArcaEmployerType"', self.source)
        self.assertIn('id="employeeArcaEmployerType" type="hidden"', self.source)

    def test_guardado_exige_un_codigo_oficial(self):
        self.assertIn('["1","4"]', self.source)
        self.assertIn('Seleccioná y confirmá el tipo de empleador ARCA', self.source)


if __name__ == "__main__":
    unittest.main()
