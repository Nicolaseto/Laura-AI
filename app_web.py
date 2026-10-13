from __future__ import annotations

import json
import mimetypes
import re
import secrets
import sqlite3
import unicodedata
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from brain import LauraEngine
from brain.game import MazeGame
from brain.storage import Memory
from brain.dataset import read_image_package
from brain.vision import (analyze_direction, choose_by_feedback, classify, classify_image,
                          decode_image, describe, feedback_signature, refine_prediction,
                          compose_learned_scene, duplicate_similarity, extract_features, generate,
                          generate_from_learning, image_to_data_url, thumbnail,
                          training_report)


ROOT = Path(__file__).resolve().parent
USER = "Nicolas"
DEFAULT_LABELS = ("greeting", "thanks", "farewell", "question", "calculation", "teaching", "positive", "negative")
laura = LauraEngine(str(ROOT / "data" / "laura.db"))
game = MazeGame()


def _plain(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value.lower())
                   if not unicodedata.combining(char))


SCENES = {"floresta", "bosque", "paisagem", "mar", "oceano", "praia", "cidade", "montanha"}
OBJECTS = {"cavalo", "cachorro", "gato", "borboleta", "morango", "garrafa", "banana", "carro", "placa"}


def _mentioned_labels(prompt: str, categories: list[dict]) -> list[str]:
    normalized = _plain(prompt)
    matches = []
    for item in categories:
        label = str(item["label"])
        if item["count"] >= 3:
            found = re.search(r"(?<!\w)" + re.escape(_plain(label)) + r"(?:s|es)?(?!\w)", normalized)
            if found:
                matches.append((found.start(), label))
    return [label for _, label in sorted(matches)]


def _load_visuals(label: str, seed: object, limit: int = 24) -> list:
    chosen = laura.memory.visual_samples(USER, label, seed, limit)
    return [decode_image(str(item["thumbnail"])) for item in chosen if item.get("thumbnail")]


def _creation_context(mode: str, subject: str, scene: str, prompt: str) -> str:
    if mode == "scene":
        return f"scene:{subject}:{scene}"[:200]
    if mode == "learned":
        return f"learned:{subject}"[:200]
    return f"procedural:{_plain(prompt).strip()[:175]}"


def _guided_choice(make_image, context: str, seed: object, use_feedback: bool = True):
    if seed is None:
        seed = secrets.token_hex(12)
    ratings = laura.memory.generation_ratings(USER, context) if use_feedback else []
    best = make_image(seed)
    if ratings:
        for i in (1, 2):
            candidate = make_image(f"{seed}-opcao-{i}")
            if choose_by_feedback([best, candidate], ratings) == 1:
                best = candidate
    return best


def relationship_name(trust: float) -> str:
    if trust >= 75:
        return "Amigo próximo"
    if trust >= 50:
        return "Amigo"
    if trust >= 25:
        return "Conhecido"
    return "Começando a conhecer"


class LauraHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, data: object, status: int = 200) -> None:
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.is_file() or ROOT not in path.resolve().parents:
            self.send_error(404)
            return
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(path)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
            content = template.replace("{{ user }}", USER).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        elif path.startswith("/static/"):
            self.send_file(ROOT / "static" / path.removeprefix("/static/"))
        elif path == "/api/memories":
            self.send_json(laura.memory.facts(USER))
        elif path == "/api/history":
            self.send_json(laura.memory.history(USER))
        elif path == "/api/learned-answers":
            self.send_json(laura.memory.learned_answers_data(USER))
        elif path == "/api/profile":
            profile = laura.memory.profile(USER)
            profile.update(name=USER, relationship=relationship_name(profile["trust"]))
            profile.update(laura.personality.status(profile))
            self.send_json(profile)
        elif path == "/api/model":
            examples = laura.memory.training_examples(USER)
            self.send_json({"custom_examples": examples, "count": len(examples), "labels": list(DEFAULT_LABELS)})
        elif path == "/api/context":
            self.send_json(laura.context.summary(USER))
        elif path == "/api/export":
            self.send_json(laura.memory.export_data(USER))
        elif path == "/api/export-previous-backup":
            previous_path = laura.memory.restore_point_path
            if not previous_path.is_file():
                self.send_json({"error": "Ainda não há uma cópia anterior à importação."}, 404)
                return
            previous = Memory(previous_path)
            try:
                self.send_json(previous.export_data(USER))
            finally:
                previous.close()
        elif path == "/api/diagnostics":
            self.send_json({**laura.memory.diagnostics(USER),
                            "has_restore_point": laura.memory.restore_point_path.is_file()})
        elif path == "/api/conflicts":
            self.send_json(laura.memory.conflicts(USER))
        elif path == "/api/vision/examples":
            self.send_json(laura.memory.visual_summary(USER))
        elif path == "/api/vision/report":
            self.send_json(training_report(laura.memory.visual_vectors(USER)))
        elif path == "/api/vision/items":
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            label = query.get("label", [None])[0]
            self.send_json(laura.memory.visual_items(USER, label))
        elif path == "/api/vision/accuracy":
            self.send_json(laura.memory.visual_accuracy(USER))
        elif path == "/api/game":
            self.send_json(game.state())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path not in ("/api/chat", "/api/feedback", "/api/import",
                        "/api/vision/import-package",
                        "/api/vision/analyze", "/api/vision/teach", "/api/vision/generate",
                        "/api/vision/rate", "/api/game/new", "/api/game/move", "/api/game/decide"):
            self.send_error(404)
            return
        try:
            # Backups visuais incluem miniaturas em base64 e podem ter vários MB.
            # Conversas continuam pequenas; apenas imagem e importação recebem limite maior.
            maximum = 142 * 1024 * 1024 if path == "/api/vision/import-package" else (
                200 * 1024 * 1024 if path == "/api/import" else (
                29 * 1024 * 1024 if path.startswith("/api/vision/") else 200_000)
            )
            length = int(self.headers.get("Content-Length", 0))
            if length > maximum:
                self.send_json({"error": "Arquivo muito grande"}, 413)
                return
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("Os dados enviados devem ser um objeto JSON.")
            if path == "/api/chat":
                self.send_json(laura.respond(str(payload.get("message", "")), USER))
            elif path == "/api/game/new":
                self.send_json(game.new(payload.get("seed")))
            elif path == "/api/game/move":
                self.send_json(game.move(str(payload.get("direction", ""))))
            elif path == "/api/game/decide":
                self.send_json(game.decide())
            elif path == "/api/feedback":
                self.send_json(laura.learn_intent(USER, str(payload.get("text", "")), str(payload.get("label", ""))))
            elif path == "/api/import":
                # Backups 1.5 com centenas de miniaturas PNG podem passar de
                # 30 MB. Durante a migração, a 1.6 compacta essas miniaturas
                # para JPEG e reduz bastante os próximos backups.
                compacted = 0
                visual_records = payload.get("visual_examples", [])
                if isinstance(visual_records, list):
                    for item in visual_records:
                        if not isinstance(item, dict):
                            continue
                        preview = str(item.get("thumbnail", ""))
                        if preview.startswith("data:image/png;base64,") and len(preview) > 12_000:
                            item["thumbnail"] = thumbnail(decode_image(preview))
                            compacted += 1
                if payload.get("format") != "laura-backup":
                    raise ValueError("backup inválido")
                try:
                    laura.memory.save_restore_point()
                except (OSError, sqlite3.Error) as error:
                    raise ValueError("Não foi possível guardar a cópia anterior. Confira o espaço livre antes de importar.") from error
                result = laura.memory.import_data(USER, payload)
                laura.retrain_classifier(USER)
                self.send_json({"imported": True, "thumbnails_compacted": compacted, **result})
            elif path == "/api/vision/import-package":
                package = read_image_package(str(payload.get("archive", "")),
                                             int(payload.get("limit_per_category", 30)))
                existing = laura.memory.visual_vectors(USER)
                accepted: list[tuple[str, list[float], str]] = []
                learned_by_category: dict[str, int] = {}
                duplicates = 0
                for label, image in package.iter_images():
                    features = extract_features(image)
                    if duplicate_similarity(features, existing, label) >= 0.985:
                        duplicates += 1
                        continue
                    accepted.append((label, features, thumbnail(image)))
                    existing.append((label, features))
                    learned_by_category[label] = learned_by_category.get(label, 0) + 1
                learned = laura.memory.add_visual_examples_bulk(USER, accepted)
                self.send_json({"imported": True, "learned": learned,
                                "duplicates": duplicates, "skipped": package.skipped,
                                "limited": package.limited,
                                "categories": learned_by_category})
            elif path == "/api/vision/analyze":
                image = decode_image(str(payload.get("image", "")))
                vectors = laura.memory.visual_vectors(USER)
                prediction = classify_image(image, vectors)
                detail_refs = [(str(item["label"]), sample)
                               for item in prediction.alternatives[:3]
                               for sample in _load_visuals(str(item["label"]), "recognition", 6)]
                prediction = refine_prediction(image, prediction, detail_refs)
                result = describe(image, prediction)
                refs = _load_visuals(prediction.label, "direction") if prediction.label else []
                direction = analyze_direction(image, refs)
                result.update(direction)
                if direction["position"] != "indeterminada":
                    result["text"] += f" Posição do objeto: {direction['position']}."
                if direction["rotation"] != "indeterminada":
                    result["text"] += f" Em relação às fotos ensinadas: {direction['rotation']}."
                else:
                    result["text"] += " Giro do objeto: não foi possível determinar com segurança."
                result["recognition_id"] = laura.memory.log_visual_recognition(
                    USER, prediction.alternatives[0]["label"] if prediction.alternatives else None,
                    prediction.confidence, prediction.known)
                self.send_json(result)
            elif path == "/api/vision/teach":
                image = decode_image(str(payload.get("image", "")))
                label = " ".join(str(payload.get("label", "")).strip().lower().split())[:60]
                if not label:
                    raise ValueError("categoria vazia")
                features = extract_features(image)
                existing = laura.memory.visual_vectors(USER)
                similarity = duplicate_similarity(features, existing, label)
                recognition_id = int(payload.get("recognition_id", 0) or 0)
                if recognition_id:
                    laura.memory.correct_visual_recognition(USER, recognition_id, label)
                if similarity >= 0.985:
                    self.send_json({"learned": False, "duplicate": True, "label": label,
                                    "similarity": round(similarity, 4)})
                    return
                example_id = laura.memory.add_visual_example(USER, label, features, thumbnail(image))
                prediction = classify(features, laura.memory.visual_vectors(USER))
                self.send_json({"learned": True, "id": example_id,
                                "duplicate": False, "label": label,
                                "confidence": prediction.confidence})
            elif path == "/api/vision/rate":
                rating = str(payload.get("rating", ""))
                context = str(payload.get("context", ""))
                generation_id = str(payload.get("generation_id", ""))
                image = decode_image(str(payload.get("image", "")))
                signature = feedback_signature(image)
                counts = laura.memory.rate_generation(USER, generation_id, context, rating, signature)
                self.send_json({"saved": True, "rating": rating, "counts": counts})
            else:
                prompt = str(payload.get("prompt", ""))
                learned_label = " ".join(str(payload.get("learned_label", "")).strip().lower().split())[:60]
                seed = payload.get("seed")
                if seed is not None and len(str(seed)) > 64:
                    raise ValueError("código da imagem muito longo")
                variation = str(payload.get("variation", "equilibrado"))
                if variation not in {"fiel", "equilibrado", "criativo"}:
                    raise ValueError("tipo de criação inválido")
                quality = str(payload.get("quality", "equilibrada"))
                if quality not in {"rapida", "equilibrada", "detalhada"}:
                    raise ValueError("qualidade inválida")
                use_feedback = payload.get("use_feedback", True)
                if not isinstance(use_feedback, bool):
                    raise ValueError("preferência de avaliação inválida")
                reference = decode_image(str(payload["reference_image"])) if payload.get("reference_image") else None
                labels = _mentioned_labels(prompt, laura.memory.visual_summary(USER)) if prompt else []
                normalized = _plain(prompt)
                scene = next((name for name in labels if _plain(name) in SCENES), None)
                subject = next((name for name in labels if name != scene), None)
                if learned_label and _plain(learned_label) not in SCENES:
                    subject = learned_label
                elif learned_label:
                    scene = learned_label
                requested_objects = [name for name in OBJECTS
                                     if re.search(r"(?<!\w)" + name + r"s?(?!\w)", normalized)]
                if len(requested_objects) > 1:
                    raise ValueError("Crie uma categoria de objeto por vez, com um cenário opcional.")
                if requested_objects and subject and not any(
                        re.search(r"(?<!\w)" + name + r"s?(?!\w)", _plain(subject))
                        for name in requested_objects):
                    raise ValueError("A categoria escolhida não corresponde ao objeto da descrição. Selecione a categoria correta ou use Somente descrição.")
                if requested_objects and subject is None:
                    raise ValueError("Ainda não aprendi esse objeto. Ensine ao menos três fotos dele na aba Imagens.")
                if subject and (scene or any(re.search(r"(?<!\w)" + name + r"(?!\w)", normalized)
                                             for name in SCENES)):
                    scene_name = scene or "desenhado"
                    context = _creation_context("scene", subject, scene_name, prompt)
                    def make_scene(candidate_seed):
                        return compose_learned_scene(prompt,
                            _load_visuals(scene, candidate_seed) if scene else [],
                            _load_visuals(subject, candidate_seed),
                            payload.get("width", 512), payload.get("height", 512),
                            candidate_seed, variation, reference, quality)
                    created = _guided_choice(make_scene, context, seed, use_feedback)
                    self.send_json({"image": image_to_data_url(created), "mode": "scene",
                                    "label": subject, "scene": scene_name, "context": context,
                                    "generation_id": secrets.token_hex(12),
                                    "examples_used": min(24, laura.memory.visual_count(USER, subject)) +
                                                     (min(24, laura.memory.visual_count(USER, scene)) if scene else 0),
                                    "variation": variation, "seed": seed})
                elif learned_label or labels:
                    label = learned_label or labels[0]
                    context = _creation_context("learned", label, "", prompt)
                    def make_learned(candidate_seed):
                        return generate_from_learning(prompt, label, _load_visuals(label, candidate_seed),
                            payload.get("width", 512), payload.get("height", 512), candidate_seed,
                            variation, reference, quality)
                    created = _guided_choice(make_learned, context, seed, use_feedback)
                    self.send_json({"image": image_to_data_url(created), "prompt": prompt,
                                    "mode": "learned", "label": label, "context": context,
                                    "generation_id": secrets.token_hex(12),
                                    "examples_used": min(24, laura.memory.visual_count(USER, label)),
                                    "method": "camadas_suaves", "variation": variation, "seed": seed})
                else:
                    if not any(re.search(r"(?<!\w)" + term + r"(?!\w)", normalized)
                               for term in SCENES | {"arvore", "espaco", "galaxia", "estrela", "planeta",
                                                     "ceu", "noite", "sol", "lua", "pixel", "mosaico", "quadrado", "agua"}):
                        raise ValueError("Ainda não sei criar isso só pela descrição. Ensine fotos da categoria ou descreva uma paisagem que conheço.")
                    context = _creation_context("procedural", "", "", prompt)
                    def make_procedural(candidate_seed):
                        created = generate(prompt, payload.get("width", 512), payload.get("height", 512), candidate_seed)
                        if reference is not None:
                            from PIL import Image, ImageOps
                            previous = ImageOps.fit(reference.convert("RGB"), created.size)
                            created = Image.blend(previous, created, .78)
                        return created
                    created = _guided_choice(make_procedural, context, seed, use_feedback)
                    self.send_json({"image": image_to_data_url(created), "prompt": prompt,
                                    "mode": "procedural", "seed": seed, "context": context,
                                    "generation_id": secrets.token_hex(12)})
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error) or "Dados inválidos"}, 400)

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/vision/ratings/"):
            generation_id = urllib.parse.unquote(path.removeprefix("/api/vision/ratings/"))
            self.send_json({"removed": laura.memory.remove_generation_rating(USER, generation_id)})
        elif path == "/api/history":
            laura.memory.clear_history(USER)
            self.send_json({"cleared": True})
        elif path.startswith("/api/memories/"):
            key = urllib.parse.unquote(path.removeprefix("/api/memories/"))
            self.send_json({"deleted": laura.memory.delete_fact(USER, key)})
        elif path.startswith("/api/vision/categories/"):
            label = urllib.parse.unquote(path.removeprefix("/api/vision/categories/"))
            self.send_json({"deleted": laura.memory.delete_visual_category(USER, label)})
        elif path.startswith("/api/vision/examples/"):
            example_id = int(path.removeprefix("/api/vision/examples/"))
            self.send_json({"deleted": laura.memory.delete_visual_example(USER, example_id)})
        else:
            self.send_error(404)

    def do_PUT(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not (path.startswith("/api/memories/") or
                path.startswith("/api/vision/categories/")):
            self.send_error(404); return
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 20_000)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if path.startswith("/api/memories/"):
                key = urllib.parse.unquote(path.removeprefix("/api/memories/"))
                value = str(payload.get("value", "")).strip()
                if not value: raise ValueError("valor vazio")
                laura.memory.remember(USER, key, value)
                self.send_json({"updated": True})
            else:
                old_label = urllib.parse.unquote(path.removeprefix("/api/vision/categories/"))
                new_label = str(payload.get("label", payload.get("new_label", "")))
                count = laura.memory.rename_visual_category(USER, old_label, new_label)
                self.send_json({"renamed": bool(count), "count": count,
                                "label": " ".join(new_label.strip().lower().split())[:60]})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error) or "Valor inválido"}, 400)


def main() -> None:
    server = HTTPServer(("127.0.0.1", 5000), LauraHandler)
    print("\nLaura 2.0 — ambiente de jogos offline")
    print("Abra no navegador: http://127.0.0.1:5000")
    print("Pressione Ctrl+C para encerrar.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLaura encerrada.")
    finally:
        server.server_close()
        laura.close()


if __name__ == "__main__":
    main()
