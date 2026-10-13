from __future__ import annotations

import random
import re

from .calculator import calculate, extract_expression
from .context import ConversationContext
from .ml_classifier import DEFAULT_EXAMPLES, build_default_classifier
from .neural_network import NeuralIntentClassifier
from .nlp import classify, normalize, similarity
from .personality import LauraPersonality
from .storage import Memory


class LauraEngine:
    def __init__(self, database: str = "data/laura.db") -> None:
        self.memory = Memory(database)
        self.pending_questions: dict[str, str] = {}
        self.context = ConversationContext()
        self.personality = LauraPersonality()
        self.classifier = build_default_classifier()
        self.neural = NeuralIntentClassifier()
        self.retrain_classifier(user="Nicolas")

    def retrain_classifier(self, user: str) -> int:
        examples = {label: list(sentences) for label, sentences in DEFAULT_EXAMPLES.items()}
        custom = self.memory.training_examples(user)
        for item in custom:
            examples.setdefault(str(item["label"]), []).append(str(item["text"]))
        self.classifier.train(examples)
        self.neural.train(examples)
        return sum(len(items) for items in examples.values())

    def learn_intent(self, user: str, text: str, label: str) -> dict[str, object]:
        if label not in DEFAULT_EXAMPLES:
            raise ValueError("intenção desconhecida")
        self.memory.add_training_example(user, text, label)
        total = self.retrain_classifier(user)
        predicted, confidence = self.classifier.predict(text)
        return {"saved": True, "predicted": predicted, "confidence": confidence, "total_examples": total}

    def _learn_fact(self, user: str, text: str) -> str | None:
        text = re.sub(r"^\s*(?:na verdade|não|nao)[,;:]?\s*", "", text, flags=re.IGNORECASE)
        patterns = [
            (r"(?:meu nome e|me chamo)\s+(.+)", "nome", "Vou lembrar que seu nome é {}."),
            (r"(?:eu moro em|moro em)\s+(.+)", "cidade", "Entendi, você mora em {}."),
            (r"(?:eu tenho|tenho)\s+(\d{1,3})\s+anos", "idade", "Vou lembrar que você tem {} anos."),
            (r"(?:eu gosto de|gosto de)\s+(.+)", "gosta_de", "Legal! Vou lembrar que você gosta de {}."),
            (r"(?:eu trabalho no|eu trabalho na|trabalho no|trabalho na)\s+(.+)", "trabalho", "Entendi. Vou lembrar que você trabalha no(a) {}."),
            (r"(?:eu estudo no|eu estudo na|estudo no|estudo na)\s+(.+)", "estudo", "Certo, vou lembrar que você estuda no(a) {}."),
        ]
        normal = normalize(text)
        for pattern, key, response in patterns:
            match = re.fullmatch(pattern, normal)
            if match:
                value = match.group(1).strip()
                self.memory.remember(user, key, value)
                return response.format(value)
        possessive = re.fullmatch(r"(?:meu|minha)\s+(.+?)\s+(?:e|eh)\s+(.+)", normal)
        if possessive:
            key, value = possessive.groups()
            self.memory.remember(user, key, value)
            return f"Certo, vou lembrar que seu/sua {key} é {value}."
        return None

    def _recall_fact(self, user: str, text: str) -> str | None:
        normal = normalize(text)
        fixed = {
            "qual e meu nome": ("nome", "Seu nome é {}."),
            "onde eu moro": ("cidade", "Você mora em {}."),
            "quantos anos eu tenho": ("idade", "Você tem {} anos."),
            "do que eu gosto": ("gosta_de", "Você me contou que gosta de {}."),
            "onde eu trabalho": ("trabalho", "Você trabalha no(a) {}."),
            "onde eu estudo": ("estudo", "Você estuda no(a) {}."),
        }
        for question, (key, response) in fixed.items():
            if similarity(normal, question) >= 0.84:
                value = self.memory.recall(user, key)
                return response.format(value) if value else "Você ainda não me contou isso."
        match = re.fullmatch(r"qual (?:e|eh) (?:meu|minha) (.+)", normal)
        if match:
            key = match.group(1)
            value = self.memory.recall(user, key)
            return f"Seu/sua {key} é {value}." if value else "Ainda não aprendi essa informação."
        return None

    def _learn_pending_answer(self, user: str, text: str) -> str | None:
        pending = self.pending_questions.get(user)
        if not pending:
            return None
        match = re.fullmatch(
            r"(?:a resposta e|a resposta eh|responda|voce deve responder)\s+(.+)",
            normalize(text),
        )
        if not match:
            return None
        answer = match.group(1).strip()
        self.memory.teach(user, normalize(pending), answer)
        self.pending_questions.pop(user, None)
        return f"Entendi! Aprendi uma resposta nova para “{pending}”."

    def _learn_answer(self, user: str, text: str) -> str | None:
        match = re.fullmatch(
            r"quando eu disser\s+(.+?)\s*,?\s*responda\s+(.+)", text, flags=re.IGNORECASE
        )
        if not match:
            return None
        question, answer = (part.strip(" \"'") for part in match.groups())
        self.memory.teach(user, normalize(question), answer)
        return f'Aprendi. Quando você disser “{question}”, responderei “{answer}”.'

    def _find_learned_answer(self, user: str, text: str) -> str | None:
        best_score, best = 0.0, None
        for row in self.memory.learned_answers(user):
            score = similarity(text, row["question"])
            if score > best_score:
                best_score, best = score, row
        if best is not None and best_score >= 0.78:
            self.memory.count_use(int(best["id"]))
            return str(best["answer"])
        return None

    def respond(self, text: str, user: str = "Nicolas") -> dict[str, str | float]:
        text = text.strip()
        if not text:
            return {"answer": "Você pode escrever alguma coisa para mim?", "intent": "empty", "confidence": 1.0}
        self.memory.log(user, "user", text)
        understood_text, context_topic = self.context.prepare(user, text)
        rude_words = {"burra", "idiota", "inutil", "estupida"}
        normalized_words = set(normalize(text).split())
        if normalized_words & rude_words:
            self.memory.update_profile(user, patience_delta=-12)
        else:
            self.memory.update_profile(user, trust_delta=0.15, patience_delta=0.4)
        rule_intent = classify(text)
        model_intent, model_confidence = self.classifier.predict(understood_text)
        neural_intent, neural_confidence = self.neural.predict(understood_text)
        learned_intent, learned_confidence = (neural_intent, neural_confidence) if neural_confidence > model_confidence else (model_intent, model_confidence)
        intent = learned_intent if rule_intent == "statement" and learned_confidence >= 0.30 else rule_intent
        answer, confidence = None, model_confidence

        if (expression := extract_expression(text)) is not None:
            try:
                answer, intent, confidence = f"O resultado é {calculate(expression)}.", "calculation", 1.0
            except (ValueError, ZeroDivisionError, SyntaxError):
                answer, intent = "Não consegui calcular essa expressão com segurança.", "calculation_error"
        answer = answer or self._learn_answer(user, text)
        answer = answer or self._learn_pending_answer(user, text)
        if answer:
            intent, confidence = ("teaching", 1.0) if intent not in ("calculation", "calculation_error") else (intent, confidence)
        answer = answer or self._recall_fact(user, text)
        if answer and intent == "question":
            intent, confidence = "memory_question", 0.95
            if answer.startswith(("Ainda", "Você ainda")):
                self.pending_questions[user] = text
                answer += " Qual seria uma boa resposta?"
        answer = answer or self._learn_fact(user, text)
        if answer and intent == "statement":
            intent, confidence = "learned_fact", 0.95
        answer = answer or self._find_learned_answer(user, understood_text)
        if answer and intent not in ("teaching", "memory_question", "learned_fact", "calculation"):
            intent, confidence = "learned_answer", 0.85

        answer = answer or self.context.special_response(user, text)
        if answer and intent not in ("calculation", "teaching", "memory_question", "learned_fact", "learned_answer"):
            intent, confidence = "context", 0.9

        profile = self.memory.profile(user)
        if not answer and intent == "greeting":
            answer, confidence = self.personality.respond(user, "greeting", profile, context_topic), 0.95
        elif not answer and intent == "thanks":
            answer, confidence = self.personality.respond(user, "thanks", profile, context_topic), 0.95
        elif not answer and intent == "farewell":
            answer, confidence = self.personality.respond(user, "farewell", profile, context_topic), 0.9
        elif not answer and intent == "positive":
            answer, confidence = self.personality.respond(user, "positive", profile, context_topic), 0.85
        elif not answer and intent == "negative":
            answer, confidence = self.personality.respond(user, "negative", profile, context_topic), 0.85
        elif not answer and profile["patience"] < 45:
            answer = self.personality.respond(user, "boundary", profile, context_topic)
            confidence = 0.2
        elif not answer:
            self.pending_questions[user] = text
            answer = self.personality.respond(user, "unknown", profile, context_topic)
            confidence = 0.2

        self.memory.log(user, "assistant", answer)
        self.context.record(user, text, answer)
        personality = self.personality.status(profile, intent)
        return {"answer": answer, "intent": intent, "confidence": confidence,
                "model_intent": model_intent, "model_confidence": model_confidence,
                "neural_intent": neural_intent, "neural_confidence": neural_confidence,
                "input": text, "context_topic": self.context.state(user).topic,
                "personality_tone": personality["tone"], "personality_mood": personality["mood"]}

    def close(self) -> None:
        self.memory.close()
