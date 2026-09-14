from __future__ import annotations

import unittest

from suite_pyside6.core.numerador_etiquetas import LabelLayout, SequenceFormatError, increment_code, sequence_values


class NumeradorEtiquetasTests(unittest.TestCase):
    def test_increment_preserves_letters_padding_and_suffix(self) -> None:
        self.assertEqual(increment_code("0009"), "0010")
        self.assertEqual(increment_code("RF-000009-A"), "RF-000010-A")


    def test_sequence_increments_exactly_one_unit(self) -> None:
        self.assertEqual(sequence_values("AB-009", 3), ("AB-009", "AB-010", "AB-011"))


    def test_sequence_requires_a_numeric_segment(self) -> None:
        with self.assertRaises(SequenceFormatError):
            sequence_values("RF-ALFA", 1)


    def test_layout_is_clamped_to_the_label_bounds(self) -> None:
        layout = LabelLayout(width_mm=50, height_mm=120, x_mm=49, y_mm=119, zone_width_mm=20, zone_height_mm=20).normalized()
        self.assertLessEqual(layout.x_mm + layout.zone_width_mm, layout.width_mm)
        self.assertLessEqual(layout.y_mm + layout.zone_height_mm, layout.height_mm)
