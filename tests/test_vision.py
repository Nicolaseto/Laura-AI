import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

from brain.storage import Memory
from brain.vision import (analyze_direction, choose_by_feedback, classify, classify_image, decode_image,
                          decode_image_bytes, refine_prediction,
                          describe, duplicate_similarity, feedback_signature,
                          compose_learned_scene, extract_features, extract_feature_variants, generate,
                          generate_from_learning, image_to_data_url, thumbnail,
                          training_report)


class VisionTests(unittest.TestCase):
    def test_object_position_and_rotation_relative_to_taught_photo(self):
        reference = Image.new("RGB", (160, 160), "white")
        ImageDraw.Draw(reference).polygon([(65, 30), (95, 30), (95, 80),
                                            (118, 80), (80, 125), (42, 80), (65, 80)], fill="black")
        self.assertEqual(analyze_direction(reference.rotate(180), [reference])["rotation"], "de ponta-cabeça")
        self.assertEqual(analyze_direction(reference.rotate(90), [reference])["rotation"], "girada à esquerda")
        shifted = Image.new("RGB", (160, 160), "white")
        ImageDraw.Draw(shifted).polygon([(7, 9), (35, 9), (35, 59),
                                         (57, 59), (42, 76), (4, 59)], fill="black")
        self.assertEqual(analyze_direction(shifted)["position"], "em cima e esquerda")
        self.assertEqual(analyze_direction(Image.new("RGB", (120, 100), "white"))["rotation"], "indeterminada")

    def test_feedback_changes_choice_and_survives_backup(self):
        liked = Image.new("RGB", (80, 80), "#35b45c")
        disliked = Image.new("RGB", (80, 80), "#d04040")
        self.assertEqual(choose_by_feedback([disliked, liked], []), 0)
        with tempfile.TemporaryDirectory() as folder:
            memory = Memory(Path(folder) / "one.db")
            context = "learned:cavalo"
            memory.rate_generation("Nicolas", "first", context, "good", feedback_signature(liked))
            memory.rate_generation("Nicolas", "second", context, "bad", feedback_signature(disliked))
            self.assertEqual(choose_by_feedback([disliked, liked], memory.generation_ratings("Nicolas", context)), 1)
            memory.rate_generation("Nicolas", "first", context, "bad", feedback_signature(liked))
            self.assertEqual(memory.feedback_counts("Nicolas", context), {"good": 0, "bad": 2})
            memory.rate_generation("Nicolas", "first", context, "good", feedback_signature(liked))
            backup = memory.export_data("Nicolas")
            memory.close()
            restored = Memory(Path(folder) / "two.db")
            restored.import_data("Nicolas", backup)
            self.assertEqual(restored.feedback_counts("Nicolas", context), {"good": 1, "bad": 1})
            self.assertEqual(choose_by_feedback([disliked, liked], restored.generation_ratings("Nicolas", context)), 1)
            legacy = dict(backup, version="1.8")
            legacy.pop("generation_feedback")
            restored.import_data("Nicolas", legacy)
            self.assertEqual(restored.feedback_counts("Nicolas", context), {"good": 0, "bad": 0})
            restored.close()

    def colored_square(self, color, mark=False):
        image = Image.new("RGB", (120, 90), color)
        if mark:
            ImageDraw.Draw(image).rectangle((35, 25, 80, 70), fill=(245, 245, 245))
        return image

    def test_encode_decode_and_description(self):
        image = self.colored_square((30, 70, 210))
        restored = decode_image(image_to_data_url(image))
        prediction = classify(extract_features(restored), [])
        result = describe(restored, prediction)
        self.assertEqual(result["orientation"], "horizontal")
        self.assertIn("azul", result["text"])

    def test_learns_visual_categories(self):
        red = self.colored_square((220, 35, 40), True)
        blue = self.colored_square((25, 65, 220), True)
        examples = [("vermelho", extract_features(red)), ("azul", extract_features(blue))]
        result = classify(extract_features(self.colored_square((215, 40, 45), True)), examples)
        self.assertEqual(result.label, "vermelho")
        self.assertGreater(result.confidence, .5)
        self.assertTrue(result.known)
        self.assertEqual(result.alternatives[0]["label"], "vermelho")

    def test_rejects_unknown_image(self):
        red = self.colored_square((220, 35, 40), True)
        blue = self.colored_square((25, 65, 220), True)
        unknown = self.colored_square((20, 220, 40))
        result = classify(extract_features(unknown), [
            ("vermelho", extract_features(red)), ("azul", extract_features(blue))])
        self.assertFalse(result.known)
        self.assertIsNone(result.label)
        self.assertEqual(len(result.alternatives), 2)

    def test_training_report(self):
        vectors = [("banana", extract_features(self.colored_square((220, 190 - i * 5, 35), i % 2 == 0)))
                   for i in range(6)]
        report = training_report(vectors)
        self.assertEqual(report[0]["label"], "banana")
        self.assertEqual(report[0]["count"], 6)
        self.assertIn(report[0]["quality"], {"bom", "repetitivo"})

    def test_visual_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Memory(Path(folder) / "first.db")
            first.add_visual_example("Nicolas", "garrafa", extract_features(self.colored_square((60, 160, 90))))
            recognition_id = first.log_visual_recognition("Nicolas", "garrafa", .82, True)
            first.correct_visual_recognition("Nicolas", recognition_id, "garrafa")
            backup = first.export_data("Nicolas")
            first.close()
            second = Memory(Path(folder) / "second.db")
            counts = second.import_data("Nicolas", backup)
            second.import_data("Nicolas", backup)
            self.assertEqual(counts["visual_examples"], 1)
            self.assertEqual(second.visual_summary("Nicolas")[0]["label"], "garrafa")
            self.assertEqual(second.visual_accuracy("Nicolas")["accuracy"], 1.0)
            self.assertEqual(second.visual_accuracy("Nicolas")["total_analyses"], 1)
            second.close()

    def test_procedural_generation(self):
        image = generate("paisagem noturna roxa")
        self.assertEqual(image.size, (512, 512))
        self.assertGreater(len(image_to_data_url(image)), 1000)

    def test_generation_from_learned_images_creates_variations(self):
        examples = [self.colored_square((40+i*12, 130+i*8, 70), i % 2 == 0)
                    for i in range(5)]
        first = generate_from_learning("desenho noturno", "floresta", examples, 384, 384, 1)
        second = generate_from_learning("desenho noturno", "floresta", examples, 384, 384, 2)
        self.assertEqual(first.size, (384, 384))
        self.assertNotEqual(first.tobytes(), second.tobytes())

    def test_generation_preserves_a_centered_shape(self):
        examples = []
        for shift in (-3, -1, 0, 2, 3):
            image = Image.new("RGB", (160, 160), (242, 242, 238))
            points = [(45+shift, 18), (115+shift, 18), (142+shift, 48),
                      (142+shift, 112), (115+shift, 142), (45+shift, 142),
                      (18+shift, 112), (18+shift, 48)]
            ImageDraw.Draw(image).polygon(points, fill=(220, 30, 35))
            examples.append(image)
        result = generate_from_learning("forma limpa", "placa", examples, 384, 384, 9)
        center = result.getpixel((192, 192))
        corner = result.getpixel((8, 8))
        self.assertGreater(center[0], center[1] * 2)
        self.assertGreater(sum(corner), sum(center))

    def test_two_learned_variations_are_visibly_different(self):
        examples = []
        for i in range(18):
            image = Image.new("RGB", (120, 120), (150 + i * 4, 185, 210 - i * 4))
            ImageDraw.Draw(image).ellipse((14 + i, 19, 90 + i, 97),
                                          fill=(30 + i * 11, 50, 120))
            examples.append(image)
        first = generate_from_learning("variação", "forma", examples, 384, 384, 101)
        second = generate_from_learning("variação", "forma", examples, 384, 384, 102)
        difference = ImageStat.Stat(ImageChops.difference(first, second)).mean
        self.assertGreater(sum(difference) / 3, 10)

    def test_creation_modes_reproduce_and_preserve_silhouette(self):
        examples = []
        for i in range(12):
            image = Image.new("RGB", (140, 140), (245, 245, 245))
            ImageDraw.Draw(image).ellipse((28 + i % 4, 22, 113 + i % 4, 115),
                                          fill=(185 + i * 3, 32 + i, 38))
            examples.append(image)
        faithful = generate_from_learning("círculo", "bola", examples, 384, 384, "mesmo", "fiel")
        repeated = generate_from_learning("círculo", "bola", examples, 384, 384, "mesmo", "fiel")
        creative = generate_from_learning("círculo", "bola", examples, 384, 384, "mesmo", "criativo")
        self.assertEqual(faithful.tobytes(), repeated.tobytes())
        self.assertNotEqual(faithful.tobytes(), creative.tobytes())
        self.assertGreater(faithful.getpixel((192, 192))[0],
                           faithful.getpixel((192, 192))[1] * 2)
        self.assertGreater(sum(faithful.getpixel((6, 6))),
                           sum(faithful.getpixel((192, 192))))
        with self.assertRaisesRegex(ValueError, "inválido"):
            generate_from_learning("círculo", "bola", examples, variation="impossível")

    def test_text_scene_places_object_over_learned_background(self):
        forests = []
        horses = []
        for i in range(5):
            forest = Image.new("RGB", (120, 120), (30 + i * 3, 110, 44))
            ImageDraw.Draw(forest).rectangle((55 + i, 10, 69 + i, 110), fill=(70, 45, 25))
            forests.append(forest)
            horse = Image.new("RGB", (120, 120), (246, 246, 246))
            ImageDraw.Draw(horse).ellipse((23 + i, 29, 91 + i, 105), fill=(143, 72, 31))
            horses.append(horse)
        first = compose_learned_scene("cavalo na floresta", forests, horses, 384, 384, "um")
        second = compose_learned_scene("cavalo na floresta", forests, horses, 384, 384, "dois")
        self.assertNotEqual(first.tobytes(), second.tobytes())
        self.assertGreater(first.getpixel((192, 180))[0], first.getpixel((192, 180))[1])
        self.assertGreater(first.getpixel((10, 10))[1], first.getpixel((10, 10))[0])

    def test_new_thumbnails_use_compact_jpeg(self):
        preview = thumbnail(self.colored_square((40, 130, 70), True).resize((900, 600)))
        restored = decode_image(preview)
        self.assertTrue(preview.startswith("data:image/jpeg;base64,"))
        self.assertEqual(restored.width, 640)
        self.assertLessEqual(restored.height, 640)

    def test_decode_large_file_exif_and_transparency(self):
        buffer = io.BytesIO()
        Image.new("RGB", (1600,1600), "green").save(buffer,"BMP")
        self.assertGreater(len(buffer.getvalue()), 6*1024*1024)
        self.assertEqual(decode_image_bytes(buffer.getvalue()).size, (1600,1600))
        buffer = io.BytesIO()
        photo = Image.new("RGB", (80,40), "red")
        exif = photo.getexif(); exif[274] = 6
        photo.save(buffer,"JPEG",exif=exif)
        self.assertEqual(decode_image_bytes(buffer.getvalue()).size,(40,80))
        buffer = io.BytesIO()
        Image.new("RGBA", (80,40), (0,0,0,0)).save(buffer,"PNG")
        self.assertEqual(decode_image_bytes(buffer.getvalue()).getpixel((0,0)),(255,255,255))

    def test_larger_generation_and_quality_modes(self):
        samples = [self.colored_square((40+i*20,130,70), True).resize((640,480)) for i in range(4)]
        quick = generate_from_learning("floresta", "floresta", samples, 1536,1152, "detail", quality="rapida")
        detailed = generate_from_learning("floresta", "floresta", samples, 1536,1152, "detail", quality="detalhada")
        self.assertEqual(detailed.size,(1536,1152))
        self.assertNotEqual(quick.tobytes(), detailed.tobytes())
        self.assertEqual(generate("paisagem", 1536,1536, 1).size,(1536,1536))
        with self.assertRaisesRegex(ValueError,"qualidade"):
            generate_from_learning("floresta","floresta",samples,quality="inexistente")

    def test_rotated_recognition_and_fine_comparison(self):
        one = Image.new("RGB", (128,128), "white")
        two = one.copy()
        ImageDraw.Draw(one).polygon([(20,25),(70,25),(70,90),(108,90),(108,108),(20,108)],fill="black")
        ImageDraw.Draw(two).ellipse((20,20,108,108),fill="black")
        examples = [("letra",extract_features(one)),("circulo",extract_features(two))]
        rotated = one.rotate(90)
        coarse = classify_image(rotated, examples)
        detailed = refine_prediction(rotated, coarse, [("letra",one),("circulo",two)])
        self.assertEqual(detailed.label,"letra")
        self.assertEqual(detailed.reason,"comparacao_detalhada")
        self.assertIs(refine_prediction(rotated, coarse, []), coarse)

    def test_learned_generation_requires_three_examples(self):
        with self.assertRaisesRegex(ValueError, "pelo menos três"):
            generate_from_learning("nova", "copo", [self.colored_square((20, 40, 60))])

    def test_feature_variants_include_rotation_and_mirror(self):
        variants = extract_feature_variants(self.colored_square((60, 160, 90), True))
        self.assertGreaterEqual(len(variants), 4)
        self.assertTrue(all(len(vector) == 88 for vector in variants))

    def test_duplicate_similarity(self):
        image = self.colored_square((60, 160, 90), True)
        features = extract_features(image)
        examples = [("garrafa", features), ("banana", features)]
        self.assertEqual(duplicate_similarity(features, examples, "garrafa"), 1.0)
        self.assertEqual(duplicate_similarity(features, examples, "teclado"), 0.0)

    def test_accuracy_history(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = Memory(Path(folder) / "accuracy.db")
            recognition_id = memory.log_visual_recognition("Nicolas", "banana", .8, True)
            self.assertTrue(memory.correct_visual_recognition("Nicolas", recognition_id, "banana"))
            stats = memory.visual_accuracy("Nicolas")
            self.assertEqual(stats["evaluated"], 1)
            self.assertEqual(stats["accuracy"], 1.0)
            memory.close()

    def test_rename_category_and_confusion_report(self):
        with tempfile.TemporaryDirectory() as folder:
            memory = Memory(Path(folder) / "rename.db")
            features = extract_features(self.colored_square((220, 190, 35)))
            memory.add_visual_example("Nicolas", "banana", features)
            recognition_id = memory.log_visual_recognition("Nicolas", "banana", .72, True)
            memory.correct_visual_recognition("Nicolas", recognition_id, "maca")
            self.assertEqual(memory.rename_visual_category("Nicolas", "banana", "fruta amarela"), 1)
            self.assertEqual(memory.visual_summary("Nicolas")[0]["label"], "fruta amarela")
            confusion = memory.visual_accuracy("Nicolas")["confusions"][0]
            self.assertEqual(confusion, {"actual": "maca", "predicted": "fruta amarela", "count": 1})
            memory.close()


if __name__ == "__main__":
    unittest.main()
