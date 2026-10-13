import tempfile
import unittest
from pathlib import Path

from brain import LauraEngine


class LauraTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.laura = LauraEngine(str(Path(self.temp.name) / "test.db"))

    def tearDown(self):
        self.laura.close()
        self.temp.cleanup()

    def test_calculation(self):
        self.assertEqual(self.laura.respond("quanto é 12 * 4?")["answer"], "O resultado é 48.")

    def test_learns_and_recalls_name(self):
        self.laura.respond("Meu nome é Nicolas", "perfil")
        result = self.laura.respond("Qual é meu nome?", "perfil")
        self.assertIn("nicolas", result["answer"].lower())

    def test_learns_answer(self):
        self.laura.respond("Quando eu disser cor favorita, responda azul", "perfil")
        self.assertEqual(self.laura.respond("cor favorita", "perfil")["answer"], "azul")

    def test_separates_users(self):
        self.laura.respond("Meu nome é Ana", "a")
        self.laura.respond("Meu nome é Bruno", "b")
        self.assertIn("ana", self.laura.respond("Qual é meu nome?", "a")["answer"].lower())
        self.assertIn("bruno", self.laura.respond("Qual é meu nome?", "b")["answer"].lower())

    def test_natural_follow_up_teaching(self):
        self.laura.respond("Qual é o melhor planeta?", "perfil")
        learned = self.laura.respond("A resposta é Terra", "perfil")
        self.assertIn("aprendi", learned["answer"].lower())
        self.assertEqual(self.laura.respond("melhor planeta", "perfil")["answer"], "terra")

    def test_natural_correction_updates_memory(self):
        self.laura.respond("Eu moro em Campinas", "perfil")
        self.laura.respond("Na verdade, eu moro em Valinhos", "perfil")
        self.assertIn("valinhos", self.laura.respond("Onde eu moro?", "perfil")["answer"].lower())


if __name__ == "__main__":
    unittest.main()
