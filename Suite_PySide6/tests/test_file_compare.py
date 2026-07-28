from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from suite_pyside6.core.file_compare.models import CompareMode, ComparisonOptions
from suite_pyside6.core.file_compare.reports import as_html, as_json, write_report
from suite_pyside6.core.file_compare.service import compare_paths
from suite_pyside6.filecompare_cli import main


def write(path: Path, data: bytes | str) -> Path:
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8", newline="")
    else:
        path.write_bytes(data)
    return path


class FileCompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_empty_and_identical_text_are_exactly_equal(self) -> None:
        self.assertTrue(compare_paths(write(self.root / "a", b""), write(self.root / "b", b"")).strict_equal)
        result = compare_paths(write(self.root / "uno.txt", "hola\n"), write(self.root / "dos.odd", "hola\n"))
        self.assertTrue(result.strict_equal)
        self.assertEqual(result.detected_type, "text")
        self.assertEqual(result.left_sha256, result.right_sha256)

    def test_text_diff_lf_spaces_and_unicode(self) -> None:
        left, right = write(self.root / "a.txt", "Árbol\nlinea dos\n"), write(self.root / "b.txt", "Árbol\r\nlinea dos  \r\n")
        strict = compare_paths(left, right)
        self.assertFalse(strict.strict_equal)
        self.assertIn("unified_diff", strict.metadata)
        relaxed = compare_paths(left, right, ComparisonOptions(CompareMode.SEMANTIC, ignore_whitespace=True, ignore_line_endings=True))
        self.assertTrue(relaxed.semantic_equal)

    def test_binary_shorter_byte_difference_and_limit(self) -> None:
        result = compare_paths(write(self.root / "a.bin", b"\x00\x01\x02"), write(self.root / "b.bin", b"\x00\xff"), ComparisonOptions(max_differences=1))
        self.assertFalse(result.strict_equal)
        self.assertTrue(result.differences[0].location.startswith("offset 1"))
        self.assertEqual(result.total_differences, 2)
        self.assertTrue(result.truncated)

    def test_large_binary_is_processed(self) -> None:
        left, right = write(self.root / "a.bin", b"x" * (2 * 1024 * 1024)), write(self.root / "b.bin", b"x" * (2 * 1024 * 1024))
        self.assertTrue(compare_paths(left, right, ComparisonOptions(block_size=65536)).strict_equal)

    def test_json_semantic_order_changed_and_invalid(self) -> None:
        options = ComparisonOptions(CompareMode.SEMANTIC)
        equal = compare_paths(write(self.root / "a.json", '{"a": 1, "b": 2}'), write(self.root / "b.json", '{"b": 2, "a": 1}'), options)
        self.assertFalse(equal.strict_equal); self.assertTrue(equal.semantic_equal)
        changed = compare_paths(write(self.root / "c.json", '{"users": [{"email":"a"}]}'), write(self.root / "d.json", '{"users": [{"email":"b"}]}'), options)
        self.assertFalse(changed.semantic_equal); self.assertEqual(changed.differences[0].location, "users[0].email")
        invalid = compare_paths(write(self.root / "invalid.json", "{"), write(self.root / "valid.json", "{}"), options)
        self.assertTrue(invalid.errors)

    def test_xml_csv_and_zip(self) -> None:
        options = ComparisonOptions(CompareMode.SEMANTIC)
        xml = compare_paths(write(self.root / "a.xml", '<root a="1"><name>A</name></root>'), write(self.root / "b.xml", '<root a="2"><name>B</name></root>'), options)
        self.assertFalse(xml.semantic_equal); self.assertTrue(any(item.kind == "xml_attribute" for item in xml.differences))
        csv_result = compare_paths(write(self.root / "a.csv", "id,name\n1,A\n"), write(self.root / "b.csv", "id,name\n1,B\n"), options)
        self.assertTrue(any(item.kind == "cell" for item in csv_result.differences))
        first, second = self.root / "a.zip", self.root / "b.zip"
        with zipfile.ZipFile(first, "w") as archive: archive.writestr("safe.txt", "uno")
        with zipfile.ZipFile(second, "w") as archive: archive.writestr("safe.txt", "dos")
        self.assertTrue(any(item.kind == "zip_changed" for item in compare_paths(first, second, options).differences))

    def test_folders_reports_cli_and_unicode_paths(self) -> None:
        left, right = self.root / "izquierda", self.root / "derecha"
        left.mkdir(); right.mkdir()
        write(left / "ñ.txt", "uno"); write(right / "ñ.txt", "dos"); write(left / "solo.txt", "x")
        result = compare_paths(left, right)
        self.assertFalse(result.strict_equal); self.assertEqual({item.kind for item in result.differences}, {"modified", "only_left"})
        report = self.root / "informe.html"; write_report(result, report, "html")
        self.assertTrue(report.exists()); self.assertIn("Comparacion", report.read_text(encoding="utf-8")); self.assertEqual(json.loads(as_json(result))["detected_type"], "directory")
        self.assertIn("<html", as_html(result))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([str(left), str(right), "--format", "json"]), 1)
        self.assertIn("directory", output.getvalue())

    def test_cli_codes_and_missing_file(self) -> None:
        same = write(self.root / "same", b"same")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(same), str(same)]), 0)
            self.assertEqual(main([str(self.root / "no-existe"), str(same)]), 2)


if __name__ == "__main__":
    unittest.main()
