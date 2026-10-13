import tempfile
import unittest
from pathlib import Path

from brain.storage import Memory


class BackupTests(unittest.TestCase):
    def test_export_import_and_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Memory(Path(folder) / "first.db")
            first.remember("Nicolas", "cidade", "Campinas")
            first.remember("Nicolas", "cidade", "Valinhos")
            first.teach("Nicolas", "cor favorita", "azul")
            first.add_training_example("Nicolas", "bom dia", "greeting")
            first.update_profile("Nicolas", trust_delta=42, patience_delta=-15)
            first.log("Nicolas", "user", "Olá, Laura")
            first.log("Nicolas", "assistant", "Olá, Nicolas")
            backup = first.export_data("Nicolas")
            self.assertEqual(len(first.conflicts("Nicolas")), 1)
            first.close()
            second = Memory(Path(folder) / "second.db")
            counts = second.import_data("Nicolas", backup)
            self.assertEqual(counts["facts"], 1)
            self.assertEqual(counts["history"], 2)
            self.assertEqual(counts["profile"], 1)
            self.assertEqual(second.recall("Nicolas", "cidade"), "Valinhos")
            self.assertEqual(second.profile("Nicolas"), {"trust": 67.0, "patience": 85.0})
            self.assertEqual(len(second.history("Nicolas")), 2)
            self.assertEqual(len(second.training_examples("Nicolas")), 1)
            self.assertEqual(len(second.conflicts("Nicolas")), 1)

            # Restaurar novamente substitui os dados e não duplica mensagens.
            second.import_data("Nicolas", backup)
            self.assertEqual(len(second.history("Nicolas")), 2)
            self.assertEqual(len(second.conflicts("Nicolas")), 1)
            self.assertEqual(second.diagnostics("Nicolas")["integrity"], "ok")
            second.close()


if __name__ == "__main__":
    unittest.main()
