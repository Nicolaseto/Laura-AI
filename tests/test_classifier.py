import unittest
import tempfile
from pathlib import Path

from brain.ml_classifier import build_default_classifier
from brain import LauraEngine
from brain.ml_classifier import DEFAULT_EXAMPLES
from brain.neural_network import NeuralIntentClassifier


class ClassifierTests(unittest.TestCase):
    def setUp(self):
        self.model = build_default_classifier()

    def test_greeting(self):
        label, confidence = self.model.predict("olá, tudo bem?")
        self.assertEqual(label, "greeting")
        self.assertGreater(confidence, 0.2)

    def test_emotion(self):
        label, _ = self.model.predict("hoje estou muito feliz")
        self.assertEqual(label, "positive")

    def test_model_can_be_retrained(self):
        self.model.train({"music": ["tocar uma música", "quero ouvir som"], "weather": ["vai chover", "previsão do tempo"]})
        self.assertEqual(self.model.predict("quero ouvir música")[0], "music")

    def test_feedback_is_persistent(self):
        with tempfile.TemporaryDirectory() as folder:
            database = str(Path(folder) / "feedback.db")
            engine = LauraEngine(database)
            result = engine.learn_intent("Nicolas", "salve minha parceira", "greeting")
            self.assertTrue(result["saved"])
            engine.close()
            reopened = LauraEngine(database)
            self.assertEqual(reopened.memory.training_examples("Nicolas")[0]["label"], "greeting")
            reopened.close()

    def test_neural_network_learns_emotions(self):
        neural = NeuralIntentClassifier()
        neural.train(DEFAULT_EXAMPLES, epochs=50)
        self.assertEqual(neural.predict("estou feliz e animado")[0], "positive")
        self.assertEqual(neural.predict("estou triste e preocupado")[0], "negative")


if __name__ == "__main__":
    unittest.main()
