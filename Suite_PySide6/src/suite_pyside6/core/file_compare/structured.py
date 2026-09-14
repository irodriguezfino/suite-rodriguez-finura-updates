from __future__ import annotations

import csv
import json
from itertools import zip_longest
from pathlib import Path
from xml.etree import ElementTree
import zipfile
from .binary import ComparisonCancelled
from ..jobs import checkpoint


def _check(result):
    checkpoint()
    callback = getattr(result, '_cancelled', None)
    if callback and callback():
        raise ComparisonCancelled()

from .detectors import detect_delimiter, detect_encoding
from .models import ComparisonOptions, ComparisonResult, Difference


def _add(result: ComparisonResult, options: ComparisonOptions, kind: str, location: str, left: object = None, right: object = None, detail: str = "") -> None:
    _check(result)
    result.add_difference(Difference(kind, location, left, right, detail), options.max_differences)


def _json_diff(left: object, right: object, path: str, result: ComparisonResult, options: ComparisonOptions) -> None:
    _check(result)
    if type(left) is not type(right):
        _add(result, options, "json_type", path, type(left).__name__, type(right).__name__)
        return
    if isinstance(left, dict):
        for key in sorted(left.keys() - right.keys()):
            _add(result, options, "json_removed", f"{path}.{key}" if path else key, left[key], None)
        for key in sorted(right.keys() - left.keys()):
            _add(result, options, "json_added", f"{path}.{key}" if path else key, None, right[key])
        for key in sorted(left.keys() & right.keys()):
            _json_diff(left[key], right[key], f"{path}.{key}" if path else key, result, options)
    elif isinstance(left, list):
        for index in range(max(len(left), len(right))):
            item_path = f"{path}[{index}]"
            if index >= len(left):
                _add(result, options, "json_added", item_path, None, right[index])
            elif index >= len(right):
                _add(result, options, "json_removed", item_path, left[index], None)
            else:
                _json_diff(left[index], right[index], item_path, result, options)
    elif left != right:
        _add(result, options, "json_changed", path or "$", left, right)


def compare_json(left: Path, right: Path, options: ComparisonOptions, result: ComparisonResult) -> None:
    encoding_left, encoding_right = detect_encoding(left) or "utf-8", detect_encoding(right) or "utf-8"
    try:
        first = json.loads(left.read_text(encoding_left))
        second = json.loads(right.read_text(encoding_right))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        result.errors.append(f"JSON no valido o no legible: {error}")
        return
    _json_diff(first, second, "", result, options)
    result.semantic_equal = result.total_differences == 0
    result.method = "comparacion semantica JSON por rutas"


def _element_children(element: ElementTree.Element) -> list[ElementTree.Element]:
    return list(element)


def _xml_diff(left: ElementTree.Element, right: ElementTree.Element, path: str, result: ComparisonResult, options: ComparisonOptions) -> None:
    _check(result)
    if left.tag != right.tag:
        _add(result, options, "xml_tag", path, left.tag, right.tag)
        return
    for attribute in left.attrib.keys() | right.attrib.keys():
        if left.attrib.get(attribute) != right.attrib.get(attribute):
            _add(result, options, "xml_attribute", f"{path}/@{attribute}", left.attrib.get(attribute), right.attrib.get(attribute))
    # XML whitespace is data unless the operator explicitly opts to ignore it.
    normalize = (lambda value: value.strip()) if options.ignore_whitespace else (lambda value: value)
    left_text, right_text = normalize(left.text or ""), normalize(right.text or "")
    if left_text != right_text:
        _add(result, options, "xml_text", path, left_text, right_text)
    if normalize(left.tail or "") != normalize(right.tail or ""):
        _add(result, options, "xml_tail", path, left.tail or "", right.tail or "")
    left_children, right_children = _element_children(left), _element_children(right)
    for index in range(max(len(left_children), len(right_children))):
        child_path = f"{path}/{left_children[index].tag if index < len(left_children) else right_children[index].tag}[{index + 1}]"
        if index >= len(left_children):
            _add(result, options, "xml_added", child_path, None, ElementTree.tostring(right_children[index], encoding="unicode"))
        elif index >= len(right_children):
            _add(result, options, "xml_removed", child_path, ElementTree.tostring(left_children[index], encoding="unicode"), None)
        else:
            _xml_diff(left_children[index], right_children[index], child_path, result, options)


def compare_xml(left: Path, right: Path, options: ComparisonOptions, result: ComparisonResult) -> None:
    try:
        first, second = ElementTree.parse(left).getroot(), ElementTree.parse(right).getroot()
    except (OSError, ElementTree.ParseError) as error:
        result.errors.append(f"XML no valido o no legible: {error}")
        return
    _xml_diff(first, second, f"/{first.tag}[1]", result, options)
    result.semantic_equal = result.total_differences == 0
    result.method = "comparacion estructural XML"


def compare_tabular(left: Path, right: Path, options: ComparisonOptions, result: ComparisonResult) -> None:
    left_encoding, right_encoding = detect_encoding(left) or "utf-8", detect_encoding(right) or "utf-8"
    try:
        left_delimiter, right_delimiter = detect_delimiter(left, left_encoding), detect_delimiter(right, right_encoding)
        with left.open("r", encoding=left_encoding, newline="") as a_stream, right.open("r", encoding=right_encoding, newline="") as b_stream:
            first = csv.reader(a_stream, delimiter=left_delimiter)
            second = csv.reader(b_stream, delimiter=right_delimiter)
            headers = []
            for row_index, (a_row, b_row) in enumerate(zip_longest(first, second, fillvalue=[])):
                _check(result)
                if row_index == 0:
                    headers = a_row
                for column_index, (a, b) in enumerate(zip_longest(a_row, b_row)):
                    if a != b:
                        column = headers[column_index] if row_index and column_index < len(headers) else str(column_index + 1)
                        _add(result, options, "cell", f"fila {row_index + 1}, columna {column}", a, b)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        result.errors.append(f"CSV/TSV no legible: {error}")
        return
    result.semantic_equal = result.total_differences == 0
    result.method = f"comparacion tabular ({left_delimiter!r} / {right_delimiter!r})"


def compare_zip(left: Path, right: Path, options: ComparisonOptions, result: ComparisonResult) -> None:
    """No extrae entradas; evita traversal y limita lecturas para no crear archivos."""
    try:
        with zipfile.ZipFile(left) as first, zipfile.ZipFile(right) as second:
            if len(first.infolist()) + len(second.infolist()) > 100_000:
                result.warnings.append("Análisis ZIP incompleto: supera el límite de 100.000 entradas.")
                return
            first_names, second_names = set(first.namelist()), set(second.namelist())
            if len(first_names) != len(first.infolist()) or len(second_names) != len(second.infolist()):
                result.errors.append("ZIP ambiguo: contiene entradas con nombres duplicados.")
                return
            if sum(item.file_size for archive in (first, second) for item in archive.infolist()) > 512 * 1024 * 1024:
                result.warnings.append("Análisis ZIP incompleto: supera el presupuesto total descomprimido de 512 MiB.")
                return
            for name in first_names - second_names:
                _add(result, options, "zip_removed", name)
            for name in second_names - first_names:
                _add(result, options, "zip_added", name)
            for name in sorted(first_names & second_names):
                _check(result)
                a, b = first.getinfo(name), second.getinfo(name)
                if a.is_dir() or b.is_dir():
                    continue
                if a.file_size > 512 * 1024 * 1024 or b.file_size > 512 * 1024 * 1024:
                    result.warnings.append(f"Entrada ZIP omitida por limite de seguridad: {name}")
                    return
                if a.file_size != b.file_size or _zip_hash(first, name, result) != _zip_hash(second, name, result):
                    _add(result, options, "zip_changed", name, a.file_size, b.file_size)
    except (OSError, zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        result.errors.append(f"ZIP no valido o no legible: {error}")
        return
    result.semantic_equal = result.total_differences == 0
    result.method = "comparacion de entradas ZIP descomprimidas"


def _zip_hash(archive: zipfile.ZipFile, name: str, result=None) -> str:
    import hashlib
    digest = hashlib.sha256()
    with archive.open(name) as stream:
        while chunk := stream.read(1024 * 1024):
            if result is not None:
                _check(result)
            digest.update(chunk)
    return digest.hexdigest()
