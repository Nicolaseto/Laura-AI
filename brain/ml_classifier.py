from __future__ import annotations

import math
from collections import Counter, defaultdict

from .nlp import normalize


DEFAULT_EXAMPLES = {
    "greeting": ["oi", "olá", "bom dia", "boa tarde", "boa noite Laura", "e aí", "como você está", "salve Laura", "opa beleza", "oi tudo bem", "olá minha amiga", "ei Laura está por aí", "fala Laura", "como vão as coisas", "podemos conversar"],
    "thanks": ["obrigado", "muito obrigado", "valeu", "agradeço", "obrigada pela ajuda", "muito grato pela ajuda", "obrigadão Laura", "você explicou muito bem", "agradeço de coração", "obrigado por me ouvir", "valeu mesmo pela resposta", "sou grato pelo seu apoio", "entendi agora obrigado", "ajudou bastante agradeço", "obrigado por tudo"],
    "farewell": ["tchau", "até mais", "até depois", "vou embora", "boa noite até amanhã", "preciso ir agora", "nos falamos mais tarde", "até logo Laura", "vou descansar depois conversamos", "foi bom conversar", "encerramos por hoje", "até a próxima conversa", "estou indo embora agora", "tchau cuide-se", "depois continuamos nossa conversa"],
    "question": ["o que você sabe", "como isso funciona", "quem é você", "onde fica", "me explique isso", "qual é a resposta", "você sabe me dizer", "por que isso acontece", "quando aconteceu", "quanto tempo demora", "qual é o maior", "onde eu moro", "do que eu gosto", "você consegue explicar", "pode responder uma pergunta"],
    "calculation": ["calcule dois mais dois", "quanto dá dez vezes três", "faça essa conta", "qual é o resultado", "resolva o cálculo", "quanto é vinte e cinco mais dezessete", "calcule doze vezes oito", "resolva cento e quarenta e quatro dividido por doze", "faça sete vezes treze", "calcule vinte menos cinco", "quanto dá duzentos e cinquenta dividido por cinco", "calcule nove elevado a dois", "resolva noventa e nove menos trinta e sete", "some dezoito e vinte e quatro", "quanto é vinte e sete vezes oito"],
    "teaching": ["vou te ensinar", "aprenda esta resposta", "a resposta é", "responda assim", "guarde este ensinamento", "lembre que", "quero ensinar algo", "quando eu disser responda", "salve esta informação", "anote isso", "você deve responder", "aprenda esta frase", "corrija sua resposta", "na verdade a resposta é", "memorize este conhecimento"],
    "positive": ["estou feliz", "isso é ótimo", "que legal", "adorei", "estou animado", "estou orgulhoso do resultado", "hoje foi um dia excelente", "estou contente com a novidade", "consegui algo que eu queria", "isso me deixou empolgado", "estou me sentindo ótimo", "que notícia maravilhosa", "deu tudo certo", "meu dia está incrível", "recebi uma notícia muito boa"],
    "negative": ["estou triste", "estou preocupado", "isso foi ruim", "estou cansado", "não estou bem", "estou nervoso e preocupado", "nada deu certo hoje", "estou me sentindo sozinho", "estou frustrado com isso", "acordei desanimado", "estou com medo", "isso está me deixando ansioso", "foi uma notícia muito ruim", "estou decepcionado", "estou passando por um momento difícil"],
}


class IntentClassifier:
    """Classificador Naive Bayes multinomial implementado sem bibliotecas externas."""

    def __init__(self) -> None:
        self.class_counts: Counter[str] = Counter()
        self.word_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.total_words: Counter[str] = Counter()
        self.vocabulary: set[str] = set()

    def train(self, examples: dict[str, list[str]]) -> None:
        self.class_counts.clear()
        self.word_counts.clear()
        self.total_words.clear()
        self.vocabulary.clear()
        for label, sentences in examples.items():
            for sentence in sentences:
                words = normalize(sentence).split()
                self.class_counts[label] += 1
                self.word_counts[label].update(words)
                self.total_words[label] += len(words)
                self.vocabulary.update(words)

    def predict(self, text: str) -> tuple[str, float]:
        words = normalize(text).split()
        if not words or not self.class_counts:
            return "statement", 0.0
        documents = sum(self.class_counts.values())
        scores: dict[str, float] = {}
        for label, count in self.class_counts.items():
            score = math.log(count / documents)
            denominator = self.total_words[label] + len(self.vocabulary)
            for word in words:
                score += math.log((self.word_counts[label][word] + 1) / denominator)
            scores[label] = score
        best = max(scores, key=scores.get)
        peak = scores[best]
        probability = 1 / sum(math.exp(value - peak) for value in scores.values())
        return best, round(probability, 4)


def build_default_classifier() -> IntentClassifier:
    classifier = IntentClassifier()
    classifier.train(DEFAULT_EXAMPLES)
    return classifier
