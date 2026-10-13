import tempfile
import unittest
from pathlib import Path

from brain import LauraEngine


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.laura = LauraEngine(str(Path(self.temp.name) / "context.db"))

    def tearDown(self):
        self.laura.close()
        self.temp.cleanup()

    def test_product_conversation(self):
        first = self.laura.respond("Eu comprei um celular novo", "Nicolas")
        self.assertIn("modelo", first["answer"].lower())
        second = self.laura.respond("Um Galaxy S25", "Nicolas")
        self.assertIn("galaxy s25", second["answer"].lower())
        third = self.laura.respond("Quanto de memória ele tem?", "Nicolas")
        self.assertIn("galaxy s25", third["answer"].lower())

    def test_context_is_separate(self):
        self.laura.respond("Eu comprei um celular", "a")
        self.assertIsNotNone(self.laura.context.state("a").topic)
        self.assertIsNone(self.laura.context.state("b").topic)

    def test_clear_context(self):
        self.laura.respond("Eu comprei um notebook", "Nicolas")
        result = self.laura.respond("Mudar de assunto", "Nicolas")
        self.assertIn("limpei", result["answer"].lower())
        self.assertIsNone(self.laura.context.state("Nicolas").topic)


if __name__ == "__main__":
    unittest.main()
