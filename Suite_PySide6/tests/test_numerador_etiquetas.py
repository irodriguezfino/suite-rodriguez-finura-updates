from __future__ import annotations

import pytest

from suite_pyside6.core.numerador_etiquetas import LabelLayout, SequenceFormatError, increment_code, sequence_values


def test_increment_preserves_letters_padding_and_suffix() -> None:
    assert increment_code("0009") == "0010"
    assert increment_code("RF-000009-A") == "RF-000010-A"


def test_sequence_increments_exactly_one_unit() -> None:
    assert sequence_values("AB-009", 3) == ("AB-009", "AB-010", "AB-011")


def test_sequence_requires_a_numeric_segment() -> None:
    with pytest.raises(SequenceFormatError):
        sequence_values("RF-ALFA", 1)


def test_layout_is_clamped_to_the_label_bounds() -> None:
    layout = LabelLayout(width_mm=50, height_mm=120, x_mm=49, y_mm=119, zone_width_mm=20, zone_height_mm=20).normalized()
    assert layout.x_mm + layout.zone_width_mm <= layout.width_mm
    assert layout.y_mm + layout.zone_height_mm <= layout.height_mm
