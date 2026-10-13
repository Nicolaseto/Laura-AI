import base64
import io
import unittest
import zipfile

from PIL import Image

from brain.dataset import read_image_package


def image_bytes(color):
    output = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(output, "JPEG")
    return output.getvalue()


def package_url(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return "data:application/zip;base64," + base64.b64encode(output.getvalue()).decode("ascii")


class DatasetTests(unittest.TestCase):
    def test_folder_names_become_categories(self):
        package = read_image_package(package_url({
            "pacote/gato/um.jpg": image_bytes((40, 80, 120)),
            "pacote/gato/dois.jpg": image_bytes((50, 90, 130)),
            "pacote/cachorro/um.jpg": image_bytes((130, 90, 40)),
        }))
        self.assertEqual(package.categories, {"gato": 2, "cachorro": 1})
        self.assertEqual(len(package.images), 3)

    def test_limit_per_category(self):
        files = {f"árvore/foto-{index}.jpg": image_bytes((20+index, 120, 50))
                 for index in range(6)}
        package = read_image_package(package_url(files), 3)
        self.assertEqual(package.categories["árvore"], 3)
        self.assertEqual(package.limited, 3)

    def test_rejects_zip_without_folder_images(self):
        with self.assertRaisesRegex(ValueError, "nenhuma imagem"):
            read_image_package(package_url({"foto.jpg": image_bytes((1, 2, 3))}))

    def test_larger_category_limit_keeps_images_compressed(self):
        raw = image_bytes((30,130,70))
        package = read_image_package(package_url({f"arvore/{i}.jpg":raw for i in range(251)}),250)
        self.assertEqual(package.categories["arvore"],250)
        self.assertEqual(package.limited,1)
        self.assertIsInstance(package.images[0][1],bytes)
        label, image = next(package.iter_images())
        self.assertEqual(label,"arvore")
        self.assertEqual(image.size,(64,48))


if __name__ == "__main__":
    unittest.main()
