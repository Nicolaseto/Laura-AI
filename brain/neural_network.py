from __future__ import annotations

import math
import random

from .nlp import normalize


class NeuralIntentClassifier:
    """Rede neural de uma camada oculta, implementada apenas com Python."""

    def __init__(self, hidden_size: int = 14, seed: int = 42) -> None:
        self.hidden_size, self.seed = hidden_size, seed
        self.vocabulary: list[str] = []
        self.labels: list[str] = []
        self.w1: list[list[float]] = []
        self.b1: list[float] = []
        self.w2: list[list[float]] = []
        self.b2: list[float] = []

    def _vector(self, text: str) -> list[float]:
        words = set(normalize(text).split())
        return [1.0 if word in words else 0.0 for word in self.vocabulary]

    @staticmethod
    def _softmax(values: list[float]) -> list[float]:
        peak = max(values)
        exps = [math.exp(value - peak) for value in values]
        total = sum(exps)
        return [value / total for value in exps]

    def train(self, examples: dict[str, list[str]], epochs: int = 35, rate: float = 0.045) -> None:
        self.labels = sorted(examples)
        self.vocabulary = sorted({word for texts in examples.values() for text in texts for word in normalize(text).split()})
        samples = [(self._vector(text), self.labels.index(label)) for label, texts in examples.items() for text in texts]
        rng = random.Random(self.seed)
        scale = 0.18
        self.w1 = [[rng.uniform(-scale, scale) for _ in self.vocabulary] for _ in range(self.hidden_size)]
        self.b1 = [0.0] * self.hidden_size
        self.w2 = [[rng.uniform(-scale, scale) for _ in range(self.hidden_size)] for _ in self.labels]
        self.b2 = [0.0] * len(self.labels)
        for _ in range(epochs):
            rng.shuffle(samples)
            for x, target in samples:
                hidden_raw = [sum(w * value for w, value in zip(row, x)) + bias for row, bias in zip(self.w1, self.b1)]
                hidden = [math.tanh(value) for value in hidden_raw]
                logits = [sum(w * value for w, value in zip(row, hidden)) + bias for row, bias in zip(self.w2, self.b2)]
                probs = self._softmax(logits)
                output_grad = [prob - (1.0 if index == target else 0.0) for index, prob in enumerate(probs)]
                hidden_grad = [sum(output_grad[o] * self.w2[o][h] for o in range(len(self.labels))) * (1 - hidden[h] ** 2) for h in range(self.hidden_size)]
                for o in range(len(self.labels)):
                    for h in range(self.hidden_size):
                        self.w2[o][h] -= rate * output_grad[o] * hidden[h]
                    self.b2[o] -= rate * output_grad[o]
                for h in range(self.hidden_size):
                    for i in range(len(self.vocabulary)):
                        self.w1[h][i] -= rate * hidden_grad[h] * x[i]
                    self.b1[h] -= rate * hidden_grad[h]

    def predict(self, text: str) -> tuple[str, float]:
        if not self.labels:
            return "statement", 0.0
        x = self._vector(text)
        hidden = [math.tanh(sum(w * value for w, value in zip(row, x)) + bias) for row, bias in zip(self.w1, self.b1)]
        probs = self._softmax([sum(w * value for w, value in zip(row, hidden)) + bias for row, bias in zip(self.w2, self.b2)])
        index = max(range(len(probs)), key=probs.__getitem__)
        return self.labels[index], round(probs[index], 4)
