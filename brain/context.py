from __future__ import annotations

import re
from dataclasses import dataclass, field

from .nlp import normalize


@dataclass
class ContextState:
    topic: str | None = None
    awaiting: str | None = None
    last_user: str | None = None
    last_answer: str | None = None
    turns: list[tuple[str, str]] = field(default_factory=list)


class ConversationContext:
    """Memória curta da conversa. É apagada quando o programa fecha."""

    def __init__(self) -> None:
        self.states: dict[str, ContextState] = {}

    def state(self, user: str) -> ContextState:
        return self.states.setdefault(user, ContextState())

    def clear(self, user: str) -> None:
        self.states[user] = ContextState()

    def prepare(self, user: str, text: str) -> tuple[str, str | None]:
        state = self.state(user)
        normal = normalize(text)
        if normal in {"mudar de assunto", "novo assunto", "esqueca esse assunto", "limpar contexto"}:
            self.clear(user)
            return text, None
        if state.topic and re.search(r"\b(ele|ela|isso|esse|essa|dele|dela)\b", normal):
            return f"{text} [assunto: {state.topic}]", state.topic
        return text, state.topic

    def special_response(self, user: str, text: str) -> str | None:
        state = self.state(user)
        normal = normalize(text)
        if normal in {"mudar de assunto", "novo assunto", "esqueca esse assunto", "limpar contexto"}:
            return "Certo, limpei o contexto atual. Sobre o que você quer conversar agora?"

        purchase = re.search(r"(?:comprei|ganhei|adquiri)\s+(?:um|uma)\s+(.+)", normal)
        if purchase:
            state.topic = purchase.group(1).strip()
            state.awaiting = "model"
            return f"Que legal! Qual é o modelo desse {state.topic}?"

        if state.awaiting == "model":
            candidate = re.sub(r"^(?:e|eh|um|uma)\s+", "", normal).strip()
            if candidate and len(candidate.split()) <= 6:
                state.topic = candidate
                state.awaiting = "opinion"
                return f"Interessante! O que você está achando do {candidate}?"

        if state.topic and re.search(r"\b(ele|ela|isso|esse|essa|dele|dela)\b", normal):
            if normal.startswith(("quanto", "qual", "como", "onde", "ele", "ela")):
                return f"Entendi que você está falando de {state.topic}, mas ainda não aprendi essa informação. Você pode me ensinar?"

        if normal in {"sim", "com certeza", "isso", "exatamente"} and state.last_answer:
            return f"Entendi. Continuamos falando sobre {state.topic}." if state.topic else "Entendi!"
        if normal in {"nao", "não", "negativo"} and state.last_answer:
            return "Certo, obrigada por esclarecer."
        if normal in {"por que", "porque", "por que isso"} and state.last_answer:
            subject = f" sobre {state.topic}" if state.topic else ""
            return f"Você quer saber o motivo do que eu disse{subject}. Pode me dizer qual parte quer que eu explique?"
        return None

    def record(self, user: str, user_text: str, answer: str) -> None:
        state = self.state(user)
        state.last_user, state.last_answer = user_text, answer
        state.turns.append((user_text, answer))
        state.turns = state.turns[-8:]

    def summary(self, user: str) -> dict[str, object]:
        state = self.state(user)
        return {"topic": state.topic, "awaiting": state.awaiting, "turns": len(state.turns)}
