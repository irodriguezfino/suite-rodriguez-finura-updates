from __future__ import annotations

from .jobs import checkpoint, checked, report_progress, begin_commit

import re
import unicodedata
from pathlib import Path

from .atomic_io import write_text_atomically, atomic_text_writer
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET
from dataclasses import dataclass, field


EXTENSIONES_EXCEL_VALIDAS = {".xlsx", ".xlsm"}
EXTENSIONES_EXCEL_NO_SOPORTADAS = {".xls", ".xlsb"}
CABECERAS_IDENTIFICACION = {
    "identificacion",
    "identificacion precinto",
    "precinto",
    "precintos",
    "numero precinto",
    "numero del precinto",
    "n precinto",
    "no precinto",
}


def normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.replace(chr(186), "o").replace(chr(170), "a")
    texto = re.sub(r"[^a-zA-Z0-9]+", " ", texto).strip().lower()
    return re.sub(r"\s+", " ", texto)


def limpiar_precinto(valor: str) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    if re.fullmatch(r"\d+(?:\.0+)?", texto):
        texto = texto.split(".", 1)[0]
    return re.sub(r"\D+", "", texto)


def columna_excel_a_indice(referencia: str) -> int:
    letras = re.sub(r"[^A-Z]", "", referencia.upper())
    indice = 0
    for letra in letras:
        checkpoint()
        indice = indice * 26 + (ord(letra) - ord("A") + 1)
    return indice - 1


def leer_valor_celda(celda, cadenas_compartidas: list[str]) -> str:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    tipo = celda.attrib.get("t")
    if tipo == "inlineStr":
        return "".join(t.text or "" for t in celda.findall(".//a:t", ns)).strip()
    valor = celda.find("a:v", ns)
    if valor is None:
        return ""
    texto = valor.text or ""
    if tipo == "s" and texto.isdigit():
        idx = int(texto)
        if 0 <= idx < len(cadenas_compartidas):
            return cadenas_compartidas[idx].strip()
    return texto.strip()


def hojas_visibles(workbook_xml: bytes) -> list[tuple[str, str]]:
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    root = ET.fromstring(workbook_xml)
    hojas = []
    for sheet in root.findall(".//a:sheet", ns):
        checkpoint()
        if sheet.attrib.get("state", "visible") != "visible":
            continue
        hojas.append((sheet.attrib.get("name", "Hoja"), sheet.attrib.get(f"{{{ns['r']}}}id", "")))
    return hojas


def relaciones_workbook(rels_xml: bytes) -> dict[str, str]:
    ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    root = ET.fromstring(rels_xml)
    rels = {}
    for rel in root.findall("r:Relationship", ns):
        checkpoint()
        rid = rel.attrib.get("Id", "")
        target = rel.attrib.get("Target", "")
        if rid and target:
            limpio = target.lstrip("/")
            if limpio.startswith("xl/"):
                rels[rid] = limpio
            elif limpio.startswith("../"):
                rels[rid] = limpio.replace("../", "", 1)
            else:
                rels[rid] = "xl/" + limpio
    return rels


def leer_precintos_excel(ruta: Path) -> tuple[list[str], str]:
    """Extrae valores de la columna Identificacion de un XLSX/XLSM."""
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        with ZipFile(ruta) as zf:
            nombres = set(zf.namelist())
            if "xl/workbook.xml" not in nombres:
                raise ValueError("no se encontro xl/workbook.xml")
            cadenas: list[str] = []
            if "xl/sharedStrings.xml" in nombres:
                if zf.getinfo("xl/sharedStrings.xml").file_size > 128 * 1024 * 1024:
                    raise ValueError("La tabla de textos supera el límite seguro de 128 MiB")
                with zf.open("xl/sharedStrings.xml") as stream:
                    for _event, si in ET.iterparse(stream, events=("end",)):
                        if si.tag == f"{{{ns['a']}}}si":
                            cadenas.append("".join(t.text or "" for t in si.findall(".//a:t", ns)).strip())
                            si.clear()
            rels = relaciones_workbook(zf.read("xl/_rels/workbook.xml.rels"))
            hojas = hojas_visibles(zf.read("xl/workbook.xml"))
            for nombre_hoja, rid in hojas:
                ruta_hoja = rels.get(rid)
                if not ruta_hoja or ruta_hoja not in nombres:
                    continue
                if zf.getinfo(ruta_hoja).file_size > 256 * 1024 * 1024:
                    raise ValueError("La hoja supera el límite seguro de 256 MiB descomprimidos")
                indice_columna = None
                precintos = []
                with zf.open(ruta_hoja) as stream:
                    for event, fila in ET.iterparse(stream, events=("end",)):
                        if fila.tag != f"{{{ns['a']}}}row":
                            continue
                        for celda in fila.findall("a:c", ns):
                            ref = celda.attrib.get("r", "")
                            if not ref:
                                continue
                            col = columna_excel_a_indice(ref)
                            if indice_columna is None:
                                valor = leer_valor_celda(celda, cadenas)
                                if normalizar_texto(valor) in CABECERAS_IDENTIFICACION or normalizar_texto(valor) == "identificacion":
                                    indice_columna = col
                                    break
                            elif col == indice_columna:
                                value = limpiar_precinto(leer_valor_celda(celda, cadenas))
                                if value:
                                    precintos.append(value)
                        fila.clear()
                if indice_columna is not None:
                    return precintos, nombre_hoja
    except BadZipFile as exc:
        raise ValueError("el archivo no parece un Excel XLSX/XLSM valido") from exc
    raise ValueError("no se encontro la columna 'Identificacion'")


def csv_precintos_windows(precintos: list[str]) -> str:
    return "".join(f"{precinto}\r\n" for precinto in precintos)


@dataclass
class ProcessResult:
    selected_files: list[Path] = field(default_factory=list)
    processed_excels: list[Path] = field(default_factory=list)
    ignored_files: list[Path] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    precintos: list[str] = field(default_factory=list)
    log_lines: list[str] = field(default_factory=list)

    @property
    def excel_count(self) -> int:
        return sum(1 for path in self.selected_files if path.suffix.lower() in EXTENSIONES_EXCEL_VALIDAS)

    @property
    def issue_count(self) -> int:
        return len(self.ignored_files) + len(self.errors)

    def summary(self) -> str:
        return (
            f"Excel encontrados: {self.excel_count} | "
            f"Procesados: {len(self.processed_excels)} | "
            f"Precintos extraidos: {len(self.precintos)} | "
            f"Ignorados/errores: {self.issue_count}"
        )

    def log_text(self) -> str:
        if not self.log_lines:
            return "Sin proceso ejecutado."
        return "Resultado del proceso:\n" + "\n".join(self.log_lines)


def process_files(paths: list[Path]) -> ProcessResult:
    result = ProcessResult(selected_files=list(paths))
    for path in checked(paths, phase="Leyendo archivos", total=len(paths), unit="archivos"):
        checkpoint()
        ext = path.suffix.lower()
        if ext not in EXTENSIONES_EXCEL_VALIDAS:
            result.ignored_files.append(path)
            if ext in EXTENSIONES_EXCEL_NO_SOPORTADAS:
                result.log_lines.append(
                    f"- Ignorado {path.name}: formato Excel antiguo/no soportado. Guarda como .xlsx."
                )
            else:
                result.log_lines.append(f"- Ignorado {path.name}: no es Excel.")
            continue

        try:
            precintos, sheet = leer_precintos_excel(path)
        except Exception as exc:
            message = f"- ERROR {path.name}: {exc}"
            result.errors.append(message)
            result.log_lines.append(message)
            continue

        result.precintos.extend(precintos)
        result.processed_excels.append(path)
        result.log_lines.append(f"- OK {path.name}: {len(precintos)} precintos desde hoja '{sheet}'.")
    return result


def write_precintos_csv(path: Path, precintos: list[str]) -> None:
    with atomic_text_writer(path, encoding="utf-8-sig") as stream:
        stream.writelines(value + "\r\n" for value in precintos)
