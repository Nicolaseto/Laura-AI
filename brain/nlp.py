from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", text))


def similarity(first: str, second: str) -> float:
    a, b = normalize(first), normalize(second)
    sequence = SequenceMatcher(None, a, b).ratio()
    ignored = {"a", "o", "as", "os", "um", "uma", "de", "do", "da", "e", "eh", "qual", "por", "favor", "voce", "pode", "me", "dizer"}
    sa, sb = set(a.split()) - ignored, set(b.split()) - ignored
    overlap = len(sa & sb) / max(1, len(sa | sb))
    contains = 1.0 if a in b or b in a else 0.0
    return 0.45 * sequence + 0.45 * overlap + 0.10 * contains


def classify(text: str) -> str:
    normal = normalize(text)
    if re.search(r"\b(oi|ola|e ai|bom dia|boa tarde|boa noite)\b", normal):
        return "greeting"
    if text.rstrip().endswith("?") or normal.startswith(("quem ", "qual ", "onde ", "como ", "quanto ", "por que ")):
        return "question"
    if re.search(r"\b(obrigado|obrigada|valeu)\b", normal):
        return "thanks"
    return "statement"
