import unittest

from brain.game import MazeGame


class GameTests(unittest.TestCase):
    def test_every_maze_is_solvable_and_agent_finishes(self):
        for seed in range(35):
            game = MazeGame()
            game.new(seed)
            for _ in range(49):
                if game.done:
                    break
                result = game.decide()
                self.assertTrue(result["last_move"]["valid"])
            self.assertTrue(game.done, f"Labirinto {seed} impossível")
            self.assertEqual(game.player, game.goal)

    def test_blocked_move_keeps_position_and_steps(self):
        game = MazeGame()
        result = game.move("left")
        self.assertFalse(result["last_move"]["valid"])
        self.assertEqual(result["player"], [0, 0])
        self.assertEqual(result["steps"], 0)

    def test_new_game_resets_progress_and_seed_reproduces_layout(self):
        game = MazeGame()
        first = game.new("exemplo")
        game.decide()
        again = game.new("exemplo")
        self.assertEqual(first["walls"], again["walls"])
        self.assertEqual(again["steps"], 0)
        self.assertEqual(again["history"], [])

    def test_invalid_direction_and_finished_game(self):
        game = MazeGame()
        with self.assertRaises(ValueError):
            game.move("diagonal")
        while not game.done:
            game.decide()
        with self.assertRaises(ValueError):
            game.decide()


if __name__ == "__main__":
    unittest.main()
