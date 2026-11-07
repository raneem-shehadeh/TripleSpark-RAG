import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from data_loader import load_chunks, resolve_page


class TestLoadChunks(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.path = Path(directory) / "chunks.json"
        self.chunk = {
            "id": "registration-1",
            "text": "  يبدأ التسجيل يوم الأحد.  ",
            "source": " دليل التسجيل.pdf ",
            "page": 3,
            "chunk_index": 0,
        }

    def load_dataset(self, chunks):
        self.path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        return load_chunks(self.path)

    def test_preserves_values_and_extra_metadata(self):
        for page in (3, " ٣ ", " iv ", "A-12", "3–5"):
            with self.subTest(page=page):
                chunk = {**self.chunk, "page": page, "metadata": {"language": "ar"}}
                self.assertEqual(self.load_dataset([chunk]), [chunk])

    def test_missing_required_fields(self):
        for field in ("id", "text", "source", "chunk_index"):
            with self.subTest(field=field):
                invalid = self.chunk.copy()
                del invalid[field]
                label = "Chunk 1" if field == "id" else r"Chunk 1 \(id='registration-1'\)"
                with self.assertRaisesRegex(ValueError, rf"{label} missing {field}$"):
                    self.load_dataset([self.chunk, invalid])

    def test_invalid_fields(self):
        invalid_values = {
            "id": ("", "  ", 1),
            "text": (" \t", None),
            "source": ("\n", []),
            "page": (True, False, 0, -1, 2.5, "  ", "0", " -١ "),
            "chunk_index": (True, False, -1, 1.0, "1"),
        }
        for field, values in invalid_values.items():
            label = "Chunk 1" if field == "id" else r"Chunk 1 \(id='registration-1'\)"
            for value in values:
                with self.subTest(field=field, value=value):
                    invalid = {**self.chunk, field: value}
                    with self.assertRaisesRegex(ValueError, rf"{label} has invalid {field}:"):
                        self.load_dataset([self.chunk, invalid])

    def test_duplicate_id(self):
        duplicate = {**self.chunk, "chunk_index": 1}
        with self.assertRaisesRegex(ValueError, r"Chunk 1 \(id='registration-1'\) has duplicate id"):
            self.load_dataset([self.chunk, duplicate])

    def test_absent_and_null_pages_are_preserved(self):
        missing = self.chunk.copy()
        del missing["page"]
        for chunk in (missing, {**self.chunk, "page": None}):
            with self.subTest(chunk=chunk):
                self.assertEqual(self.load_dataset([chunk]), [chunk])
                self.assertEqual(resolve_page(chunk), "Unknown")

    def test_resolves_explicit_page_metadata(self):
        cases = (
            ({"source_page": 55}, "55"),
            ({"page": "74 و127–128"}, "74 و127–128"),
            ({"source_pages": [60, 98, 99]}, "60, 98, 99"),
            ({"page_reference": "ص 77–78"}, "ص 77–78"),
            ({"page_reference": "ص 92 وما بعدها"}, "ص 92 وما بعدها"),
            ({"source_reference": "المادة 11، ص 80–81"}, "ص 80–81"),
            ({"source_reference": "المادة 11", "source_ref": "turn874949view0"}, "Unknown"),
            ({"source_pages": [60, True], "source_page": -1, "page_reference": "ص 0–5"}, "Unknown"),
        )
        for metadata, expected in cases:
            with self.subTest(metadata=metadata):
                self.assertEqual(resolve_page({"page": None, "metadata": metadata}), expected)
        self.assertEqual(resolve_page({"page": "iv", "metadata": {"source_page": 55}}), "iv")
