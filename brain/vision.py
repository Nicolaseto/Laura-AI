from __future__ import annotations

import base64
import colorsys
import io
import math
import random
import re
import secrets
import unicodedata
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps


MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 64_000_000
MAX_OUTPUT_SIZE = 1536
MAX_PROCESSING_SIDE = 2048
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "GIF"}


def decode_image_bytes(raw: bytes) -> Image.Image:
    """Abre bytes de imagem aplicando os mesmos limites da interface."""
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise ValueError("imagem vazia ou maior que 20 MB")
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in ALLOWED_FORMATS:
            raise ValueError("formato não suportado")
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValueError("resolução maior que 64 megapixels")
        # Check before decoding the full image; JPEG can shrink during decoding.
        image.draft("RGB", (MAX_PROCESSING_SIDE, MAX_PROCESSING_SIDE))
        image.thumbnail((MAX_PROCESSING_SIDE, MAX_PROCESSING_SIDE), _resample())
        image.load()
        image = ImageOps.exif_transpose(image)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba, mask=rgba.getchannel("A"))
            return background
        return image.convert("RGB")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("formato de imagem inválido") from exc


def decode_image(data_url: str) -> Image.Image:
    """Decodifica uma imagem enviada pelo navegador com limites seguros."""
    encoded = data_url.split(",", 1)[-1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("imagem inválida") from exc
    return decode_image_bytes(raw)


def image_to_data_url(image: Image.Image) -> str:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def image_to_jpeg_data_url(image: Image.Image, quality: int = 78) -> str:
    """Compacta exemplos visuais sem deixar o backup pesado demais no celular."""
    output = io.BytesIO()
    image.convert("RGB").save(output, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _resample() -> int:
    return getattr(Image, "Resampling", Image).BILINEAR


def _pixels(image: Image.Image):
    """Compatível com Pillow atual e com a futura remoção de getdata()."""
    flattened = getattr(image, "get_flattened_data", None)
    return flattened() if flattened else image.getdata()


def extract_features(image: Image.Image) -> list[float]:
    """Extrator visual próprio: cores por regiões, histogramas e contornos."""
    sample = image.convert("RGB").resize((16, 16), _resample())
    pixels = list(_pixels(sample))
    features: list[float] = []

    # Mapa espacial 4x4, com a média RGB de cada região.
    for gy in range(4):
        for gx in range(4):
            block = [pixels[y * 16 + x] for y in range(gy * 4, gy * 4 + 4)
                     for x in range(gx * 4, gx * 4 + 4)]
            for channel in range(3):
                features.append(sum(p[channel] for p in block) / (16 * 255))

    # Histograma RGB: ajuda quando o objeto muda um pouco de posição.
    for channel in range(3):
        bins = [0] * 8
        for pixel in pixels:
            bins[min(7, pixel[channel] // 32)] += 1
        features.extend(value / 256 for value in bins)

    # Contornos horizontais e verticais médios por região.
    gray = [sum(pixel) / 3 / 255 for pixel in pixels]
    for gy in range(4):
        for gx in range(4):
            edges = []
            for y in range(gy * 4, gy * 4 + 4):
                for x in range(gx * 4, gx * 4 + 4):
                    i = y * 16 + x
                    if x < 15:
                        edges.append(abs(gray[i] - gray[i + 1]))
                    if y < 15:
                        edges.append(abs(gray[i] - gray[i + 16]))
            features.append(sum(edges) / max(1, len(edges)))
    return features


def auto_crop(image: Image.Image) -> Image.Image:
    """Tenta separar o objeto de um fundo relativamente uniforme."""
    preview = image.convert("RGB").resize((128, 128), _resample())
    pixels = list(_pixels(preview))
    border = ([pixels[x] for x in range(128)] + [pixels[127 * 128 + x] for x in range(128)] +
              [pixels[y * 128] for y in range(128)] + [pixels[y * 128 + 127] for y in range(128)])
    background = tuple(sum(pixel[c] for pixel in border) / len(border) for c in range(3))
    points = []
    for y in range(128):
        for x in range(128):
            pixel = pixels[y * 128 + x]
            if sum(abs(pixel[c] - background[c]) for c in range(3)) > 75:
                points.append((x, y))
    if len(points) < 128 * 128 * .04 or len(points) > 128 * 128 * .88:
        return image
    left, top = min(x for x, _ in points), min(y for _, y in points)
    right, bottom = max(x for x, _ in points), max(y for _, y in points)
    margin = 7
    left, top = max(0, left - margin), max(0, top - margin)
    right, bottom = min(127, right + margin), min(127, bottom + margin)
    scale_x, scale_y = image.width / 128, image.height / 128
    return image.crop((round(left * scale_x), round(top * scale_y),
                       max(1, round((right + 1) * scale_x)), max(1, round((bottom + 1) * scale_y))))


def extract_feature_variants(image: Image.Image) -> list[list[float]]:
    """Variações baratas tornam o reconhecimento menos sensível ao ângulo e ao fundo."""
    original = image.convert("RGB")
    cropped = auto_crop(original)
    candidates = [original, ImageOps.mirror(original),
                  original.rotate(8, resample=_resample(), expand=False),
                  original.rotate(-8, resample=_resample(), expand=False)]
    candidates.extend(original.rotate(angle, expand=True) for angle in (90, 180, 270))
    if cropped.size != original.size:
        candidates.extend([cropped, ImageOps.mirror(cropped)])
        candidates.extend(cropped.rotate(angle, expand=True) for angle in (90, 180, 270))
    return [extract_features(candidate) for candidate in candidates]


def classify_image(image: Image.Image, examples: list[tuple[str, list[float]]]) -> Prediction:
    predictions = [classify(vector, examples) for vector in extract_feature_variants(image)]
    return max(predictions, key=lambda item: (item.known, item.confidence))


def refine_prediction(image: Image.Image, prediction: Prediction,
                      references: list[tuple[str, Image.Image]]) -> Prediction:
    """Recheck close candidates using a finer image grid and quarter turns.

    A fallback preserves the original decision unless the finer comparison is
    both close and separated. Similarity is a heuristic, not a calibrated probability.
    """
    if not references:
        return prediction

    def vector(sample):
        return [channel / 255 for pixel in _pixels(sample.convert("RGB").resize((32, 32), _resample()))
                for channel in pixel]

    candidates = []
    for source in (image, auto_crop(image)):
        for angle in (0, 90, 180, 270):
            rotated = source.rotate(angle, expand=True)
            candidates.extend((vector(rotated), vector(ImageOps.mirror(rotated))))
    by_label = {}
    for label, reference in references:
        for sample in (reference, auto_crop(reference)):
            values = vector(sample)
            distance = min(sum(abs(a-b) for a,b in zip(values, other))/len(values)
                           for other in candidates)
            by_label[label] = min(distance, by_label.get(label, 1.0))
    ranking = sorted(by_label.items(), key=lambda pair: pair[1])
    label, best = ranking[0]
    margin = ranking[1][1] - best if len(ranking) > 1 else 1.0
    if best > .12 or margin < .025:
        return prediction
    confidence = min(.97, max(.5, 1 - best * 3))
    alternatives = [{"label": name, "confidence": round(min(.97, max(0, 1-score*3)),4),
                     "distance": round(score,4)} for name, score in ranking]
    return Prediction(label, confidence, ranking, alternatives, True, "comparacao_detalhada")


def _distance(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return float("inf")
    # A versão 1.4 equilibra cor, distribuição e contornos. Os contornos
    # recebiam pouco peso apenas por ocuparem menos posições no vetor.
    spatial = sum((a - b) ** 2 for a, b in zip(left[:48], right[:48])) / 48
    histogram = sum((a - b) ** 2 for a, b in zip(left[48:72], right[48:72])) / 24
    edges = sum((a - b) ** 2 for a, b in zip(left[72:], right[72:])) / 16
    return math.sqrt(spatial * .44 + histogram * .26 + edges * .30)


def duplicate_similarity(features: list[float], examples: list[tuple[str, list[float]]],
                         label: str) -> float:
    """Retorna 0..1; valores muito altos indicam foto repetida ou quase idêntica."""
    distances = [_distance(features, vector) for example_label, vector in examples
                 if example_label == label]
    if not distances:
        return 0.0
    return max(0.0, min(1.0, 1.0 - min(distances) / 0.08))


@dataclass
class Prediction:
    label: str | None
    confidence: float
    distances: list[tuple[str, float]]
    alternatives: list[dict[str, object]]
    known: bool
    reason: str


def classify(features: list[float], examples: list[tuple[str, list[float]]]) -> Prediction:
    if not examples:
        return Prediction(None, 0.0, [], [], False, "sem_exemplos")

    by_label: dict[str, list[float]] = {}
    all_distances = []
    for label, vector in examples:
        distance = _distance(features, vector)
        by_label.setdefault(label, []).append(distance)
        all_distances.append((label, distance))

    # Compara cada categoria pela média dos três exemplos mais próximos.
    category_distances: list[tuple[str, float]] = []
    for label, distances in by_label.items():
        nearest_for_label = sorted(distances)[:3]
        category_distances.append((label, sum(nearest_for_label) / len(nearest_for_label)))
    category_distances.sort(key=lambda item: item[1])

    raw_scores = [(label, math.exp(-7.5 * distance)) for label, distance in category_distances]
    total = sum(score for _, score in raw_scores) or 1.0
    alternatives = []
    for (label, distance), (_, raw) in zip(category_distances[:3], raw_scores[:3]):
        probability = raw / total
        similarity = max(0.0, 1.0 - distance / 0.48)
        confidence = min(0.99, probability * 0.55 + similarity * 0.45)
        alternatives.append({"label": label, "confidence": round(confidence, 4),
                             "distance": round(distance, 4)})

    best = alternatives[0]
    second_probability = raw_scores[1][1] / total if len(raw_scores) > 1 else 0.0
    best_probability = raw_scores[0][1] / total
    margin = best_probability - second_probability
    close_enough = float(best["distance"]) <= 0.34
    separated = len(by_label) == 1 or (best_probability >= 0.43 and margin >= 0.055)
    known = close_enough and separated
    reason = "reconhecida" if known else ("imagem_muito_diferente" if not close_enough else "categorias_parecidas")
    return Prediction(str(best["label"]) if known else None, float(best["confidence"]),
                      sorted(all_distances, key=lambda item: item[1])[:5], alternatives, known, reason)


def training_report(examples: list[tuple[str, list[float]]]) -> list[dict[str, object]]:
    grouped: dict[str, list[list[float]]] = {}
    for label, vector in examples:
        grouped.setdefault(label, []).append(vector)
    centroids = {label: [sum(values) / len(vectors) for values in zip(*vectors)]
                 for label, vectors in grouped.items()}
    report = []
    for label, vectors in sorted(grouped.items()):
        sample = random.Random(label).sample(vectors, min(32, len(vectors)))
        pair_distances = [_distance(sample[i], sample[j]) for i in range(len(sample))
                          for j in range(i + 1, len(sample))]
        diversity = sum(pair_distances) / len(pair_distances) if pair_distances else 0.0
        count = len(vectors)
        if count < 3:
            quality, tip = "iniciante", "Ensine pelo menos três imagens."
        elif count < 6:
            quality, tip = "básico", "Adicione mais ângulos, fundos e iluminações."
        elif diversity < 0.035:
            quality, tip = "repetitivo", "As imagens são parecidas; use fotos mais variadas."
        elif count >= 10 and diversity >= 0.07:
            quality, tip = "excelente", "A categoria tem quantidade e variedade muito boas."
        else:
            quality, tip = "bom", "O treinamento já está adequado; novas variações ainda ajudam."
        neighbours = sorted(((_distance(centroids[label], vector), other)
                             for other, vector in centroids.items() if other != label))
        closest_distance, closest_label = neighbours[0] if neighbours else (None, None)
        if closest_distance is not None and closest_distance < .075:
            tip = f"Está parecida com “{closest_label}”. Ensine fundos e ângulos mais diferentes."
        report.append({"label": label, "count": count, "diversity": round(diversity, 4),
                       "quality": quality, "tip": tip, "closest_label": closest_label,
                       "separation": round(closest_distance, 4) if closest_distance is not None else None})
    return report


COLOR_NAMES = {
    "vermelho": (220, 55, 55), "laranja": (235, 135, 45), "amarelo": (230, 210, 55),
    "verde": (65, 175, 90), "ciano": (50, 190, 205), "azul": (65, 105, 210),
    "roxo": (145, 80, 190), "rosa": (225, 105, 160), "marrom": (120, 80, 55),
    "cinza": (130, 130, 130), "preto": (25, 25, 30), "branco": (235, 235, 235),
}


def nearest_color(rgb: tuple[int, int, int]) -> str:
    return min(COLOR_NAMES, key=lambda name: sum((a - b) ** 2 for a, b in zip(rgb, COLOR_NAMES[name])))


def describe(image: Image.Image, prediction: Prediction) -> dict[str, object]:
    sample = image.resize((64, 64), _resample())
    pixels = list(_pixels(sample))
    average = tuple(round(sum(p[i] for p in pixels) / len(pixels)) for i in range(3))
    brightness = sum(average) / 3
    luminances = [sum(pixel) / 3 for pixel in pixels]
    contrast = (sum((value - brightness) ** 2 for value in luminances) / len(luminances)) ** 0.5
    orientation = "quadrada" if abs(image.width - image.height) / max(image.size) < .08 else (
        "horizontal" if image.width > image.height else "vertical")
    light = "escura" if brightness < 85 else "clara" if brightness > 175 else "com luminosidade média"
    contrast_name = "contraste forte" if contrast > 65 else "contraste suave" if contrast < 32 else "contraste médio"
    color = nearest_color(average)
    if prediction.known and prediction.label:
        text = (f"Parece ser {prediction.label} ({round(prediction.confidence * 100)}% de confiança). "
                f"É uma imagem {orientation}, {light}, com {contrast_name} e predominância de {color}.")
    elif prediction.alternatives:
        candidate = prediction.alternatives[0]
        text = (f"Não tenho confiança suficiente para afirmar o objeto. A possibilidade mais próxima é "
                f"{candidate['label']} ({round(float(candidate['confidence']) * 100)}%), mas a imagem pode ser desconhecida. "
                f"Vejo uma imagem {orientation}, {light}, com {contrast_name} e predominância de {color}.")
    else:
        text = (f"Ainda não reconheço o objeto. Vejo uma imagem {orientation}, {light}, "
                f"com {contrast_name} e predominância de {color}. Ensine-me a categoria para eu aprender.")
    return {"text": text, "width": image.width, "height": image.height,
            "orientation": orientation, "brightness": round(brightness),
            "contrast": round(contrast), "dominant_color": color,
            "rgb": list(average), "label": prediction.label,
            "confidence": round(prediction.confidence, 4), "known": prediction.known,
            "reason": prediction.reason, "alternatives": prediction.alternatives}


def thumbnail(image: Image.Image) -> str:
    copy = image.copy()
    # New examples keep more detail; old backups remain readable as they are.
    copy.thumbnail((640, 640), getattr(Image, "Resampling", Image).LANCZOS)
    return image_to_jpeg_data_url(copy, quality=85)


def _direction_mask(image: Image.Image) -> Image.Image | None:
    """Foreground only when the border is close to a single color."""
    sample = image.convert("RGB").resize((96, 96), _resample())
    background = _border_color(sample)
    pixels = list(_pixels(sample))
    border = ([pixels[x] for x in range(96)] + [pixels[95 * 96 + x] for x in range(96)] +
              [pixels[y * 96] for y in range(96)] + [pixels[y * 96 + 95] for y in range(96)])
    if sum(sum(abs(p[c] - background[c]) for c in range(3)) for p in border) / len(border) > 62:
        return None
    mask = Image.new("L", (96, 96))
    mask.putdata([255 if sum(abs(p[c] - background[c]) for c in range(3)) > 72 else 0
                  for p in pixels])
    area = sum(value > 0 for value in _pixels(mask)) / (96 * 96)
    bounds = mask.getbbox()
    if not bounds or not .04 <= area <= .78 or (bounds[2]-bounds[0] >= 90 and bounds[3]-bounds[1] >= 58):
        return None
    return mask


def analyze_direction(image: Image.Image, references: list[Image.Image] | None = None) -> dict[str, str]:
    """Position on canvas and rotation relative to a confidently segmented taught image."""
    mask = _direction_mask(image)
    if mask is None:
        return {"position": "indeterminada", "rotation": "indeterminada"}
    bounds = mask.getbbox()
    cx = (bounds[0] + bounds[2]) / 192
    cy = (bounds[1] + bounds[3]) / 192
    horizontal = "esquerda" if cx < .40 else "direita" if cx > .60 else ""
    vertical = "em cima" if cy < .40 else "embaixo" if cy > .60 else ""
    position = " e ".join(filter(None, (vertical, horizontal))) or "centro"
    rotation = "indeterminada"
    if references:
        # Use only consistent asymmetric silhouettes; a circle cannot reveal rotation.
        def shape(value: Image.Image) -> Image.Image:
            box = value.getbbox()
            return ImageOps.contain(value.crop(box), (32, 32), _resample()).resize((32, 32), _resample())

        target = shape(mask)
        candidates = []
        for reference in references[:16]:
            reference_mask = _direction_mask(reference)
            if reference_mask is None:
                continue
            oriented = [shape(reference_mask.rotate(angle, expand=True)) for angle in (0, 90, 180, 270)]
            scores = [sum(abs(a-b) for a, b in zip(_pixels(target), _pixels(other))) / (32*32*255)
                      for other in oriented]
            ordered = sorted(range(4), key=lambda i: scores[i])
            if scores[ordered[0]] < .24 and scores[ordered[1]] - scores[ordered[0]] > .045:
                candidates.append((ordered[0], scores[ordered[0]]))
        if candidates:
            candidates.sort(key=lambda item: item[1])
            best = candidates[:min(5, len(candidates))]
            winner = min(range(4), key=lambda i: (-sum(item[0] == i for item in best),
                                                   sum(item[1] for item in best if item[0] == i)))
            if sum(item[0] == winner for item in best) > len(best) / 2:
                rotation = ("como nos exemplos", "girada à esquerda", "de ponta-cabeça",
                            "girada à direita")[winner]
    return {"position": position, "rotation": rotation}


def feedback_signature(image: Image.Image) -> list[float]:
    """Small coarse image fingerprint for choosing among local variations."""
    sample = ImageOps.fit(image.convert("RGB"), (12, 12), method=_resample())
    return [round(channel / 255, 3) for pixel in _pixels(sample) for channel in pixel]


def choose_by_feedback(candidates: list[Image.Image], ratings: list[dict[str, object]]) -> int:
    """Prefer similarity to likes and distance from dislikes, among already created options."""
    usable = [(item["rating"], item["signature"]) for item in ratings
              if item.get("rating") in ("good", "bad") and isinstance(item.get("signature"), list)
              and len(item["signature"]) == 432]
    if not usable:
        return 0

    def distance(a: list[float], b: list[float]) -> float:
        return sum(abs(x-y) for x, y in zip(a, b)) / len(a)

    def score(image: Image.Image) -> float:
        signature = feedback_signature(image)
        positives = [distance(signature, prior) for rating, prior in usable if rating == "good"]
        negatives = [distance(signature, prior) for rating, prior in usable if rating == "bad"]
        return (min(negatives) if negatives else 0) - (min(positives) if positives else 0)

    return max(range(len(candidates)), key=lambda index: score(candidates[index]))


def _prompt_color(prompt: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    for name, rgb in COLOR_NAMES.items():
        if name in prompt:
            return rgb
    return default


def _has_any(prompt: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(word)}(?!\w)", prompt) for word in words)


def generate(prompt: str, width: int = 512, height: int = 512,
             seed: int | str | None = None) -> Image.Image:
    """Gerador procedural determinístico, leve e inteiramente offline."""
    prompt = prompt.lower().strip()
    if not prompt:
        raise ValueError("descreva a imagem")
    width = min(MAX_OUTPUT_SIZE, max(256, int(width)))
    height = min(MAX_OUTPUT_SIZE, max(256, int(height)))
    rng = random.Random(f"{prompt}|{seed if seed is not None else 'fixo'}")
    image = Image.new("RGB", (width, height), (10, 15, 35))
    draw = ImageDraw.Draw(image)
    main = _prompt_color(prompt, (91, 102, 230))
    accent = tuple(min(255, value + 70) for value in main)

    if _has_any(prompt, ("floresta", "árvore", "arvore", "bosque")):
        for y in range(height):
            t = y / height
            draw.line((0, y, width, y), fill=(round(30 + 65*t), round(95 + 80*t), round(125 - 55*t)))
        for layer in range(3):
            for _ in range(12 + layer * 7):
                x = rng.randrange(-20, width + 20); base = rng.randrange(height // 2, height + 50)
                trunk = max(3, width // 100 + layer * 2); crown = rng.randrange(width // 25, width // 10)
                draw.rectangle((x-trunk, base-crown*2, x+trunk, base), fill=(65, 45, 35))
                leaf = tuple(max(0, min(255, value + rng.randint(-35, 35))) for value in main)
                draw.ellipse((x-crown, base-crown*3, x+crown, base-crown), fill=leaf)
    elif _has_any(prompt, ("cidade", "prédio", "predio", "urbano")):
        night = "noite" in prompt or "noturna" in prompt
        sky = (12, 18, 48) if night else (80, 165, 225)
        image.paste(sky, (0, 0, width, height))
        x = 0
        while x < width:
            building_width = rng.randint(max(25, width//16), max(45, width//8)); top = rng.randint(height//4, height*2//3)
            shade = tuple(max(8, value-rng.randint(35, 90)) for value in main)
            draw.rectangle((x, top, x+building_width, height), fill=shade)
            for wy in range(top+12, height-10, 18):
                for wx in range(x+9, x+building_width-6, 15):
                    if rng.random() > .35: draw.rectangle((wx, wy, wx+5, wy+7), fill=(255, 220, 105) if night else (150, 205, 235))
            x += building_width + rng.randint(2, 8)
    elif _has_any(prompt, ("espaço", "espaco", "galáxia", "galaxia", "estrela", "planeta")):
        image.paste((5, 7, 25), (0, 0, width, height))
        for _ in range(max(80, width//3)):
            x, y = rng.randrange(width), rng.randrange(height); light = rng.randrange(150, 256)
            draw.ellipse((x, y, x+rng.choice((1, 1, 2)), y+rng.choice((1, 2))), fill=(light, light, min(255, light+20)))
        radius = min(width, height)//5; x, y = width*2//3, height//2
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=main, outline=accent, width=max(2,width//150))
        draw.arc((x-radius*2, y-radius//2, x+radius*2, y+radius//2), 5, 175, fill=accent, width=max(2,width//100))
    elif _has_any(prompt, ("mar", "oceano", "praia", "água", "agua")):
        horizon = height * 2 // 5
        image.paste((80, 175, 235), (0, 0, width, horizon)); image.paste(main, (0, horizon, width, height))
        for y in range(horizon, height, max(8, height//35)):
            offset = rng.randint(-25, 25)
            for x in range(offset, width, max(35, width//9)):
                draw.arc((x, y, x+width//8, y+height//18), 190, 350, fill=accent, width=max(1,width//220))
    elif _has_any(prompt, ("paisagem", "montanha", "céu", "noite", "sol", "lua")):
        night = "noite" in prompt or "lua" in prompt
        top = (8, 12, 42) if night else (55, 155, 230)
        bottom = (95, 55, 145) if night else (255, 190, 105)
        for y in range(height):
            t = y / max(1, height - 1)
            color = tuple(round(a * (1 - t) + b * t) for a, b in zip(top, bottom))
            draw.line((0, y, width, y), fill=color)
        orb = (235, 240, 220) if night else (255, 225, 90)
        draw.ellipse((width * .68, height * .12, width * .84, height * .28), fill=orb)
        for layer in range(3):
            base = height * (.62 + layer * .1)
            points = [(0, height)]
            for x in range(0, width + 1, max(30, width // 8)):
                points.append((x, base - rng.randint(20, 100)))
            points.extend([(width, height)])
            shade = tuple(max(0, value - 25 * layer) for value in main)
            draw.polygon(points, fill=shade)
    elif _has_any(prompt, ("pixel", "mosaico", "quadrado")):
        size = max(16, width // 16)
        for y in range(0, height, size):
            for x in range(0, width, size):
                hue = (colorsys.rgb_to_hsv(*(v / 255 for v in main))[0] + rng.uniform(-.12, .12)) % 1
                rgb = tuple(round(v * 255) for v in colorsys.hsv_to_rgb(hue, rng.uniform(.45, .9), rng.uniform(.45, 1)))
                draw.rectangle((x, y, x + size, y + size), fill=rgb)
    else:
        # Arte abstrata: gradiente, círculos e linhas guiados pelo texto.
        for y in range(height):
            t = y / height
            color = tuple(round(v * (.28 + .72 * t)) for v in main)
            draw.line((0, y, width, y), fill=color)
        for _ in range(28):
            radius = rng.randint(max(8, width // 35), max(20, width // 7))
            x, y = rng.randint(-radius, width), rng.randint(-radius, height)
            color = tuple(max(0, min(255, value + rng.randint(-70, 70))) for value in accent)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=color, width=max(2, width // 170))
        for _ in range(12):
            draw.line((rng.randrange(width), rng.randrange(height), rng.randrange(width), rng.randrange(height)),
                      fill=accent, width=max(1, width // 250))
    return ImageEnhance.Contrast(image).enhance(1.08)


def _border_color(image: Image.Image) -> tuple[int, int, int]:
    sample = image.convert("RGB").resize((48, 48), _resample())
    pixels = list(_pixels(sample))
    border = ([pixels[x] for x in range(48)] + [pixels[47 * 48 + x] for x in range(48)] +
              [pixels[y * 48] for y in range(48)] + [pixels[y * 48 + 47] for y in range(48)])
    return tuple(round(sum(pixel[channel] for pixel in border) / len(border))
                 for channel in range(3))


def _prepare_learned_sample(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Centraliza objetos separáveis; fotos comuns mantêm o enquadramento inteiro."""
    original = image.convert("RGB")
    cropped = auto_crop(original)
    if cropped.size != original.size:
        canvas = Image.new("RGB", size, _border_color(original))
        limit = (max(1, round(size[0] * .86)), max(1, round(size[1] * .86)))
        fitted = ImageOps.contain(cropped, limit, method=_resample())
        position = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
        canvas.paste(fitted, position)
        return canvas
    return ImageOps.fit(original, size, method=_resample())


def _average_images(images: list[Image.Image]) -> Image.Image:
    average = images[0].copy()
    for index, sample in enumerate(images[1:], 2):
        average = Image.blend(average, sample, 1 / index)
    return average


def _organic_mask(size: tuple[int, int], rng: random.Random) -> Image.Image:
    """Máscara de regiões grandes e suaves, sem a grade visível da versão 1.5."""
    grid = Image.new("L", (6, 6))
    grid.putdata([rng.randrange(0, 256) for _ in range(36)])
    mask = grid.resize(size, getattr(Image, "Resampling", Image).BICUBIC)
    mask = mask.filter(ImageFilter.GaussianBlur(max(5, min(size) // 18)))
    return ImageEnhance.Contrast(mask).enhance(1.6)


def _soft_patch(size: tuple[int, int], rng: random.Random) -> Image.Image:
    """Escolhe uma região irregular grande, sem deixar bordas de azulejos."""
    w, h = size
    radius_x, radius_y = rng.randint(w // 7, w // 3), rng.randint(h // 7, h // 3)
    x, y = rng.randrange(w), rng.randrange(h)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((x-radius_x, y-radius_y, x+radius_x, y+radius_y), fill=210)
    return mask.filter(ImageFilter.GaussianBlur(max(8, min(w, h) // 32)))


def _object_mask(image: Image.Image, size: tuple[int, int]) -> tuple[Image.Image, tuple[int, int, int]] | None:
    """Isola uma silhueta quando as bordas têm fundo quase uniforme."""
    analysis_size = (96, 96)
    sample = image.resize(analysis_size, _resample())
    background = _border_color(sample)
    pixels = list(_pixels(sample))
    border = ([pixels[x] for x in range(96)] + [pixels[95 * 96 + x] for x in range(96)] +
              [pixels[y * 96] for y in range(96)] + [pixels[y * 96 + 95] for y in range(96)])
    if sum(sum(abs(p[c] - background[c]) for c in range(3)) for p in border) / len(border) > 62:
        return None
    values = [max(0, min(255, (sum(abs(p[c] - background[c]) for c in range(3)) - 40) * 4))
              for p in pixels]
    foreground = sum(v >= 128 for v in values) / len(values)
    if not .07 <= foreground <= .78:
        return None
    check = Image.new("L", analysis_size)
    check.putdata([255 if value >= 128 else 0 for value in values])
    bounds = check.getbbox()
    if bounds is None or ((bounds[2] - bounds[0]) >= 90 and
                          (bounds[3] - bounds[1]) >= 58):
        # Uma paisagem inteira com céu e chão não é o contorno do objeto.
        return None
    mask = Image.new("L", analysis_size)
    mask.putdata(values)
    mask = mask.filter(ImageFilter.MaxFilter(5)).resize(
        size, getattr(Image, "Resampling", Image).BICUBIC)
    return mask.filter(ImageFilter.GaussianBlur(max(2, min(size) // 110))), background


def _move_subject(image: Image.Image, mask: Image.Image, background: tuple[int, int, int],
                  rng: random.Random) -> tuple[Image.Image, Image.Image]:
    """Altera enquadramento e direção da silhueta junto com o conteúdo."""
    if rng.random() < .5:
        image, mask = ImageOps.mirror(image), ImageOps.mirror(mask)
    width, height = image.size
    zoom = rng.uniform(.86, 1.13)
    dx, dy = rng.uniform(-.065, .065) * width, rng.uniform(-.055, .055) * height
    transform = (1 / zoom, 0, width * (1 - 1 / zoom) / 2 - dx / zoom,
                 0, 1 / zoom, height * (1 - 1 / zoom) / 2 - dy / zoom)
    affine = getattr(Image, "Transform", Image).AFFINE
    image = image.transform((width, height), affine, transform,
                            resample=getattr(Image, "Resampling", Image).BICUBIC,
                            fillcolor=background)
    mask = mask.transform((width, height), affine, transform,
                          resample=getattr(Image, "Resampling", Image).BICUBIC,
                          fillcolor=0)
    return image, mask


def _reinforce_structure(image: Image.Image, reference: Image.Image) -> Image.Image:
    """Reforça contornos comuns com baixa intensidade, sem desenhar uma grade."""
    smooth = reference.convert("L").filter(ImageFilter.GaussianBlur(.7))
    edges = ImageOps.autocontrast(smooth.filter(ImageFilter.FIND_EDGES))
    edges = edges.point(lambda value: 0 if value < 62 else min(52, (value - 62) // 3))
    edges = edges.filter(ImageFilter.GaussianBlur(.45))
    dark = Image.new("RGB", image.size, (12, 14, 20))
    return Image.composite(dark, image, edges)


def generate_from_learning(prompt: str, label: str, examples: list[Image.Image],
                           width: int = 512, height: int = 512,
                           seed: int | str | None = None,
                           variation: str = "equilibrado",
                           reference: Image.Image | None = None,
                           quality: str = "equilibrada") -> Image.Image:
    """Cria uma composição coerente em camadas usando exemplos ensinados."""
    if len(examples) < 3:
        raise ValueError("ensine pelo menos três imagens desta categoria antes de criar")
    if variation not in {"fiel", "equilibrado", "criativo"}:
        raise ValueError("tipo de criação inválido")
    if quality not in {"rapida", "equilibrada", "detalhada"}:
        raise ValueError("qualidade inválida")
    width = min(MAX_OUTPUT_SIZE, max(256, int(width))); height = min(MAX_OUTPUT_SIZE, max(256, int(height)))
    prompt = prompt.lower().strip() or f"nova imagem de {label}"
    rng = random.Random(f"aprendido|{label}|{prompt}|{seed if seed is not None else secrets.randbits(64)}")
    work_limit = {"rapida": 384, "equilibrada": 512, "detalhada": 768}[quality]
    scale = min(1.0, work_limit / max(width, height))
    work_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    # Cada criação sorteia exemplos de toda a categoria. Nenhuma foto serve
    # como camada dominante: cada região pode vir de uma origem diferente.
    count = {"fiel": 7, "equilibrado": 10, "criativo": 14}[variation]
    chosen = rng.sample(examples, min(len(examples), count))
    prepared = [_prepare_learned_sample(image, work_size) for image in chosen]
    result = _average_images(prepared[:3])
    for sample in prepared[3:]:
        result = Image.composite(sample, result, _organic_mask(work_size, rng))
    for _ in range({"fiel": 4, "equilibrado": 8, "criativo": 13}[variation]):
        sample = rng.choice(prepared)
        result = Image.composite(sample, result, _soft_patch(work_size, rng))
    # Uma máscara controla apenas a borda externa; o interior continua uma
    # combinação de várias imagens, preservando variação sem copiar a foto.
    outlines = [candidate for sample in prepared
                if (candidate := _object_mask(sample, work_size)) is not None]
    result = _reinforce_structure(result, _average_images(prepared))
    if outlines:
        mask, color = rng.choice(outlines)
        result, mask = _move_subject(result, mask, color, rng)
        if variation != "fiel":
            mask = mask.point(lambda value: round(value * (.9 if variation == "equilibrado" else .65)))
        background = Image.new("RGB", work_size, color)
        result = Image.composite(result, background, mask)

    if _has_any(prompt, ("desenho", "ilustração", "ilustracao", "pintura")):
        result = ImageOps.posterize(result, 5).filter(ImageFilter.SMOOTH_MORE)
    if _has_any(prompt, ("pixel", "pixelado")):
        small = result.resize((max(32, width//16), max(32, height//16)), _resample())
        result = small.resize((width, height), getattr(Image, "Resampling", Image).NEAREST)
    if _has_any(prompt, ("noite", "noturno", "escuro")):
        result = ImageEnhance.Brightness(result).enhance(.58)
    elif _has_any(prompt, ("claro", "ensolarado", "brilhante")):
        result = ImageEnhance.Brightness(result).enhance(1.18)
    tint = _prompt_color(prompt, (0, 0, 0))
    if tint != (0, 0, 0):
        overlay = Image.new("RGB", result.size, tint)
        result = Image.blend(result, overlay, .12)
    result = ImageEnhance.Sharpness(ImageEnhance.Contrast(result).enhance(1.10)).enhance(1.16)
    if result.size != (width, height):
        result = result.resize((width, height), getattr(Image, "Resampling", Image).LANCZOS)
    if reference is not None:
        previous = ImageOps.fit(reference.convert("RGB"), (width, height), method=_resample())
        result = Image.blend(previous, result, .75)
    return result


def compose_learned_scene(prompt: str, scene_examples: list[Image.Image],
                          subject_examples: list[Image.Image], width: int = 512,
                          height: int = 512, seed: str | int | None = None,
                          variation: str = "equilibrado",
                          reference: Image.Image | None = None,
                          quality: str = "equilibrada") -> Image.Image:
    """Usa a paisagem aprendida ao fundo e recorta um objeto aprendido à frente."""
    if (scene_examples and len(scene_examples) < 3) or len(subject_examples) < 3:
        raise ValueError("ensine pelo menos três fotos de cada categoria da cena")
    if quality not in {"rapida", "equilibrada", "detalhada"}:
        raise ValueError("qualidade inválida")
    width, height = min(MAX_OUTPUT_SIZE, max(256, int(width))), min(MAX_OUTPUT_SIZE, max(256, int(height)))
    size = (width, height)
    rng = random.Random(f"cena|{prompt}|{seed}")
    background = (generate_from_learning(prompt, "cenário", scene_examples,
                                         width, height, seed, variation, quality=quality)
                  if scene_examples else generate(prompt, width, height, seed))
    # Tenta várias fotografias: a separação só funciona quando existe contraste
    # entre objeto e borda. Nunca cola uma foto retangular sobre a paisagem.
    candidates = rng.sample(subject_examples, min(len(subject_examples), 16))
    for subject in candidates:
        detail = {"rapida": 256, "equilibrada": 384, "detalhada": 640}[quality]
        preview = ImageOps.pad(subject.convert("RGB"), (detail, detail), method=_resample(),
                               color=_border_color(subject))
        result = _object_mask(preview, preview.size)
        if result is None:
            continue
        mask, color = result
        bounds = mask.point(lambda value: 255 if value > 100 else 0).getbbox()
        if bounds is None:
            continue
        pixels = list(_pixels(mask.crop(bounds)))
        if sum(value > 100 for value in pixels) / len(pixels) > .88:
            continue
        subject = preview.crop(bounds)
        mask = mask.crop(bounds).filter(ImageFilter.MinFilter(5))
        instruction = "".join(c for c in unicodedata.normalize("NFKD", prompt.lower())
                              if not unicodedata.combining(c)).replace("-", " ")
        if "de ponta cabeca" in instruction:
            subject, mask = subject.rotate(180), mask.rotate(180)
        target = (round(width * rng.uniform(.40, .56)), round(height * .56))
        subject = ImageOps.contain(subject, target, method=getattr(Image, "Resampling", Image).LANCZOS)
        mask = mask.resize(subject.size, getattr(Image, "Resampling", Image).BICUBIC)
        if rng.random() < .5:
            subject, mask = ImageOps.mirror(subject), ImageOps.mirror(mask)
        x = round(width * rng.uniform(.36, .61) - subject.width / 2)
        y = round(height * rng.uniform(.87, .94) - subject.height)
        if re.search(r"\besquerda\b", instruction):
            x = round(width * .05)
        elif re.search(r"\bdireita\b", instruction):
            x = round(width * .95 - subject.width)
        elif "no centro" in instruction:
            x = round((width - subject.width) / 2)
        if any(term in instruction for term in ("em cima", "no alto", "no topo")):
            y = round(height * .05)
        elif any(term in instruction for term in ("embaixo", "em baixo", "na parte inferior")):
            y = round(height * .95 - subject.height)
        elif "no centro" in instruction:
            y = round((height - subject.height) / 2)
        layer = Image.new("RGB", size, color)
        alpha = Image.new("L", size, 0)
        layer.paste(subject, (x, y))
        alpha.paste(mask, (x, y))
        background.paste(layer, (0, 0), alpha)
        if reference is not None:
            background = Image.blend(ImageOps.fit(reference.convert("RGB"), size,
                                                 method=_resample()), background, .78)
        return background
    raise ValueError("Não consegui separar o objeto das fotos. Ensine fotos com o objeto inteiro sobre um fundo simples.")
