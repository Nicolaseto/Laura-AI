"""Ambiente de labirinto da série 2; decisões ainda usam busca simples."""

from collections import deque
from random import Random
import secrets


DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
LABELS = {"up": "cima", "down": "baixo", "left": "esquerda", "right": "direita"}


class MazeGame:
    size = 7

    def __init__(self):
        self.new()

    def new(self, seed=None):
        self.seed = str(seed) if seed is not None else secrets.token_hex(6)
        if len(self.seed) > 64:
            raise ValueError("Código da partida muito longo.")
        rng = Random(self.seed)
        self.player = (0, 0)
        self.goal = (self.size - 1, self.size - 1)
        # Garante sempre um caminho, sem depender de tentativas aleatórias.
        path = {self.player, self.goal}
        x = y = 0
        while (x, y) != self.goal:
            if x == self.size - 1 or (y < self.size - 1 and rng.random() < .5):
                y += 1
            else:
                x += 1
            path.add((x, y))
        self.walls = {(x, y) for y in range(self.size) for x in range(self.size)
                      if (x, y) not in path and rng.random() < .29}
        self.steps = 0
        self.done = False
        self.history = []
        return self.state()

    def state(self):
        return {"size": self.size, "player": list(self.player), "goal": list(self.goal),
                "walls": [list(p) for p in sorted(self.walls)], "steps": self.steps,
                "done": self.done, "seed": self.seed, "history": self.history[-20:]}

    def move(self, direction, actor="Você"):
        if direction not in DIRECTIONS:
            raise ValueError("Direção inválida.")
        if self.done:
            raise ValueError("A partida terminou. Comece uma nova.")
        dx, dy = DIRECTIONS[direction]
        x, y = self.player
        target = (x + dx, y + dy)
        valid = (0 <= target[0] < self.size and 0 <= target[1] < self.size
                 and target not in self.walls)
        if valid:
            self.player = target
            self.steps += 1
            self.done = target == self.goal
        event = {"actor": actor, "direction": direction, "valid": valid,
                 "message": (f"{actor} foi para {LABELS[direction]}." if valid else
                             f"{actor} tentou ir para {LABELS[direction]}, mas havia um obstáculo.")}
        if self.done:
            event["message"] += " Chegou ao objetivo!"
        self.history.append(event)
        return {**self.state(), "last_move": event}

    def decide(self):
        """Busca em largura, sem treinamento ou recompensa (base da versão 2.0)."""
        if self.done:
            raise ValueError("A partida terminou. Comece uma nova.")
        queue = deque([(self.player, None)])
        seen = {self.player}
        while queue:
            point, first = queue.popleft()
            if point == self.goal and first:
                return self.move(first, "Laura")
            for direction, (dx, dy) in DIRECTIONS.items():
                next_point = (point[0] + dx, point[1] + dy)
                if (next_point not in seen and next_point not in self.walls
                        and 0 <= next_point[0] < self.size
                        and 0 <= next_point[1] < self.size):
                    seen.add(next_point)
                    queue.append((next_point, first or direction))
        raise ValueError("Não há caminho livre até o objetivo.")
