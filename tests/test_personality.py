import unittest

from brain.personality import LauraPersonality


class PersonalityTests(unittest.TestCase):
    def setUp(self):
        self.personality = LauraPersonality(seed=7)

    def test_tone_changes_with_trust(self):
        low = self.personality.status({"trust": 20, "patience": 100})
        high = self.personality.status({"trust": 80, "patience": 100})
        self.assertEqual(low["tone"], "educado")
        self.assertEqual(high["tone"], "próximo")

    def test_empathy_changes_mood(self):
        state = self.personality.status({"trust": 50, "patience": 100}, "negative")
        self.assertEqual(state["mood"], "acolhedora")

    def test_avoids_immediate_repetition(self):
        profile = {"trust": 50, "patience": 100}
        first = self.personality.respond("Nicolas", "greeting", profile)
        second = self.personality.respond("Nicolas", "greeting", profile)
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
