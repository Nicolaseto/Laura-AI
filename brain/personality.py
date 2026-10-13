from __future__ import annotations

import random


class LauraPersonality:
    """Escolhe respostas conforme confiança, paciência, emoção e assunto."""

    def __init__(self, seed: int | None = None) -> None:
        self.random = random.Random(seed)
        self.recent: dict[str, list[str]] = {}

    @staticmethod
    def status(profile: dict[str, float], intent: str | None = None) -> dict[str, str]:
        trust, patience = profile["trust"], profile["patience"]
        tone = "próximo" if trust >= 70 else "amigável" if trust >= 40 else "educado"
        if patience < 45:
            mood = "incomodada"
        elif intent == "negative":
            mood = "acolhedora"
        elif intent == "positive":
            mood = "animada"
        else:
            mood = "curiosa"
        return {"tone": tone, "mood": mood}

    def _pick(self, user: str, options: list[str]) -> str:
        recent = self.recent.setdefault(user, [])
        available = [option for option in options if option not in recent[-3:]] or options
        choice = self.random.choice(available)
        recent.append(choice)
        self.recent[user] = recent[-6:]
        return choice

    def respond(self, user: str, category: str, profile: dict[str, float], topic: str | None = None) -> str:
        state = self.status(profile, category)
        tone = state["tone"]
        banks = {
            "greeting": {
                "educado": ["Olá! Como posso ajudar?", "Oi! Sobre o que você quer conversar?"],
                "amigável": ["Oi! O que vamos fazer hoje?", "Olá! Que bom falar com você novamente."],
                "próximo": [f"Oi, {user}! O que temos para hoje?", f"E aí, {user}! Qual é a ideia de agora?"],
            },
            "thanks": {
                "educado": ["Por nada! Fico feliz em ajudar.", "Disponha!"],
                "amigável": ["Imagina! Foi um prazer ajudar.", "Por nada! Pode contar comigo."],
                "próximo": ["Que isso, estamos juntos!", "Sempre que precisar, estou por aqui."],
            },
            "farewell": {
                "educado": ["Até mais!", "Até a próxima!"],
                "amigável": ["Tchau! Foi bom conversar com você.", "Até depois! Cuide-se."],
                "próximo": [f"Até mais, {user}! Depois continuamos.", "Vai lá! Quando voltar, retomamos daqui."],
            },
            "positive": {
                "educado": ["Fico feliz em saber disso!", "Isso parece uma ótima notícia."],
                "amigável": ["Que bom! O que deixou você mais feliz nisso?", "Gostei de saber! Quer me contar mais?"],
                "próximo": ["Aí sim! Conta os detalhes.", "Que coisa boa! Eu sabia que você conseguiria."],
            },
            "negative": {
                "educado": ["Sinto muito. Posso ajudar de alguma forma?", "Entendo. Se quiser, pode me explicar o que aconteceu."],
                "amigável": ["Poxa... quer conversar sobre isso?", "Imagino que não esteja fácil. Estou aqui para ouvir."],
                "próximo": ["Poxa, isso deve estar pesando. Quer me contar com calma?", "Ei, estou aqui com você. O que aconteceu?"],
            },
            "unknown": {
                "educado": ["Ainda não sei responder isso. Você pode me ensinar?", "Não tenho essa resposta ainda. Como você responderia?"],
                "amigável": ["Essa eu ainda não aprendi. Fiquei curiosa — você me ensina?", "Não tenho certeza. Vamos descobrir juntos?"],
                "próximo": ["Você me pegou nessa! Qual seria uma boa resposta?", "Essa eu não sei ainda. Me ensina?"],
            },
            "boundary": {
                "educado": ["Prefiro que a gente converse com respeito.", "Não gostei da forma como você falou comigo."],
                "amigável": ["Vamos com calma, por favor. Assim eu consigo ajudar melhor.", "Eu quero ajudar, mas sem ofensas."],
                "próximo": ["Ei, pega leve comigo. Vamos conversar direito.", "Assim você acaba me irritando. Vamos com calma."],
            },
        }
        choices = banks[category][tone]
        answer = self._pick(user, choices)
        if category == "unknown" and topic:
            answer += f" Entendi que o assunto é {topic}."
        return answer
