from __future__ import annotations

import csv
import json
from pathlib import Path
import zipfile
from xml.etree import ElementTree


TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".py", ".js", ".ts", ".css", ".html", ".htm", ".ini", ".cfg", ".toml", ".yaml", ".yml", ".sql", ".sh", ".bat"}


def _sample(path: Path, size: int = 65536) -> bytes:
    with path.open("rb") as stream:
        return stream.read(size)


def is_probably_text(sample: bytes) -> bool:
    if b"\x00" in sample:
        return False
    if not sample:
        return True
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return all(byte in (9, 10, 13) or 32 <= byte < 127 for byte in sample)


def detect_encoding(path: Path) -> str | None:
    sample = _sample(path)
    for encoding in ("utf-8-sig", "utf-16", "utf-8", "cp1252", "latin-1"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return None


def detect_type(path: Path) -> str:
    try:
        sample = _sample(path)
    except OSError:
        return "unknown"
    suffix = path.suffix.lower()
    if sample.startswith(b"%PDF-"):
        return "pdf"
    if sample.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a", b"BM")):
        return "image"
    if zipfile.is_zipfile(path):
        return "zip"
    if suffix == ".json":
        return "json"
    if suffix == ".xml":
        return "xml"
    if sample.lstrip().startswith(b"<"):
        try:
            ElementTree.fromstring(sample)
            return "xml"
        except ElementTree.ParseError:
            pass
    if suffix in {".csv", ".tsv"}:
        return "csv" if suffix == ".csv" else "tsv"
    if suffix in TEXT_EXTENSIONS or is_probably_text(sample):
        return "text"
    return "binary"


def detect_delimiter(path: Path, encoding: str) -> str:
    sample = path.read_text(encoding=encoding, errors="replace")[:65536]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return "\t" if path.suffix.lower() == ".tsv" else ","
